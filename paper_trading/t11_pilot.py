"""Offline T11 pilot proposal/journal seam. No credentials, network or broker writes.

This does not generate T11 signals or replace native execution state. An adapter
must independently qualify features, enforce session bounds and reconcile native
state before handing these intents to a broker. Existing SPY code is untouched.
"""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import os
from pathlib import Path

SYMBOLS = frozenset('AGG BIL BND BTAL IEF IOO KMLM PSQ QLD QQQ SH SOXL SOXS SPXL SQQQ TECL TECS TLT TQQQ UVXY VTV XLF XLK SPY'.split())
CAPITAL = Decimal('10000')
DEPLOYMENT = Decimal('.90')
POLICY_HASH = '56ff1d5255a9ed80deb10cb62711db1c627df8b2f0cb3c82632a49678ed0f431'
TERMINAL = frozenset({'filled', 'canceled', 'expired', 'rejected'})


class PilotError(ValueError):
    pass


def number(value):
    try:
        value = Decimal(str(value))
    except Exception:
        raise PilotError('Invalid numeric observation.') from None
    if not value.is_finite():
        raise PilotError('Nonfinite observation.')
    return value


def aware(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        raise PilotError('Invalid timestamp.') from None
    if result.tzinfo is None:
        raise PilotError('Timezone required.')
    return result


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def proposal(decision, quotes, *, now, next_open, cash, capital=CAPITAL):
    """Return offline opening-auction LIMIT proposals; never submit/queue them.

    Adapter supplies authoritative broker next_open (including holiday calendar).
    This core rejects stale quotes, future/incomplete signals and auction cutoff.
    Decision uses BASE weights, so the traffic-light cap is applied exactly once.
    """
    now, opening = aware(now), aware(next_open)
    if not timedelta(minutes=2) < opening - now <= timedelta(minutes=10):
        raise PilotError('Prepare only 09:20–before09:28 ET relative to broker open.')
    capital, cash = number(capital), number(cash)
    if not 0 < capital <= CAPITAL or cash < capital:
        raise PilotError('Pilot capital/cash outside flat-start bounds.')
    if decision.get('policy_sha256') != POLICY_HASH or decision.get('qualification') != 'verified':
        raise PilotError('Qualified pinned policy decision required.')
    available = aware(decision['available_at'])
    close = aware(decision['input_close'])
    if not close <= available <= now or not timedelta(0) < now - close <= timedelta(days=4):
        raise PilotError('Incomplete, future or stale signal.')
    cap = number(decision['gate_cap'])
    if cap not in (Decimal(0), Decimal('.5'), Decimal(1)):
        raise PilotError('Invalid gate cap.')
    weights = {s: number(w) for s, w in decision['base_weights'].items()}
    if len(weights) > 3 or any(s not in SYMBOLS or not 0 < w <= 1 for s, w in weights.items()):
        raise PilotError('Invalid target universe/weights.')
    if sum(weights.values(), Decimal(0)) > Decimal('1.000000000001'):
        raise PilotError('Base weights exceed one.')
    # Reserve USD2 per possible order in addition to the 10% undeployed cash.
    budget = max(Decimal(0), capital * DEPLOYMENT * cap - 2 * len(weights))
    orders = []
    for symbol, weight in sorted(weights.items()):
        if cap == 0:
            continue
        quote = quotes[symbol]
        bid, ask = number(quote['bid']), number(quote['ask'])
        age = now - aware(quote['timestamp'])
        if not 0 < bid <= ask or not timedelta(0) <= age <= timedelta(seconds=10) or (ask-bid)/ask > Decimal('.01'):
            raise PilotError('Invalid, wide or stale quote.')
        limit = (ask * Decimal('1.0025')).quantize(Decimal('.01'), rounding='ROUND_CEILING')
        qty = int((budget * weight / limit).to_integral_value(rounding=ROUND_FLOOR))
        if qty:
            orders.append({'symbol': symbol, 'qty': str(qty), 'side': 'buy',
                           'type': 'limit', 'time_in_force': 'opg',
                           'limit_price': str(limit), 'extended_hours': False})
    result = {'schema': 1, 'kind': 'offline_proposal_not_authorization',
              'decision_sha256': hashlib.sha256(canonical(decision)).hexdigest(),
              'next_open': opening.isoformat(), 'prepared_at': now.isoformat(),
              'capital': str(capital), 'gate_cap': str(cap), 'orders': orders,
              'execution_parity': False, 'order_bearing_ready': False}
    result['proposal_sha256'] = hashlib.sha256(canonical(result)).hexdigest()
    return result


class IntentJournal:
    """Exclusive offline intent evidence; atomic replace and directory fsync.

    Every uncertain reservation stays nonterminal. Reconciliation records cumulative
    fills, never an incremental fill stream; native event emission is not implemented.
    Single writer: lock collision fails closed, including after a process crash.
    """
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = self.root / 'writer.lock'

    def _write(self, path, obj):
        tmp = self.root / '.pending'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(obj)); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp, path)
            fd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except BaseException:
            # Preserve temporary evidence if any operation was interrupted.
            raise

    def _mutate(self, action):
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise PilotError('Writer lock exists; inspect without deleting evidence.') from None
        os.close(fd)
        try:
            return action()
        finally:
            self.lock.unlink()

    def reserve(self, order, proposal_hash):
        """Record one intent; identical reservation is rejected, never retried."""
        if len(proposal_hash) != 64 or any(c not in '0123456789abcdef' for c in proposal_hash):
            raise PilotError('Invalid proposal fingerprint.')
        if order.get('symbol') not in SYMBOLS or order.get('side') != 'buy' or order.get('type') != 'limit' or order.get('time_in_force') != 'opg' or order.get('extended_hours') is not False:
            raise PilotError('Unsupported intent.')
        qty, price = number(order['qty']), number(order['limit_price'])
        if qty <= 0 or qty != int(qty) or price <= 0 or qty * price > CAPITAL * DEPLOYMENT:
            raise PilotError('Invalid intent quantity/price.')
        client = 't11p-' + hashlib.sha256(canonical([proposal_hash, order])).hexdigest()[:36]
        path = self.root / (client + '.json')
        def write():
            if path.exists():
                raise PilotError('Intent already reserved; reconcile, do not resubmit.')
            self._write(path, {'client_order_id': client, 'order': order,
                              'proposal_sha256': proposal_hash, 'status': 'reserved_unknown',
                              'filled_qty': '0', 'observations': []})
            return client
        return self._mutate(write)

    def reconcile(self, client, broker):
        if not client.startswith('t11p-') or len(client) != 41 or any(c not in '0123456789abcdef' for c in client[5:]):
            raise PilotError('Invalid client identity.')
        path = self.root / (client + '.json')
        def write():
            state = json.loads(path.read_text())
            order = state['order']
            for key in ('symbol', 'side', 'type', 'time_in_force'):
                if broker.get(key) != order[key]:
                    raise PilotError('Broker identity mismatch.')
            if broker.get('client_order_id') != client or number(broker['qty']) != number(order['qty']) or number(broker['limit_price']) != number(order['limit_price']):
                raise PilotError('Broker identity/limit mismatch.')
            filled, previous = number(broker['filled_qty']), number(state['filled_qty'])
            if not previous <= filled <= number(order['qty']):
                raise PilotError('Cumulative fill regressed or exceeded request.')
            status = broker.get('status')
            if status not in TERMINAL | {'new', 'accepted', 'partially_filled', 'pending_cancel', 'pending_new'}:
                raise PilotError('Unknown broker state; reservation remains unresolved.')
            if state['status'] in TERMINAL and (status != state['status'] or filled != previous):
                raise PilotError('Terminal observation changed; manual review required.')
            if status == 'filled' and filled != number(order['qty']):
                raise PilotError('Incomplete terminal fill.')
            average = number(broker.get('filled_avg_price') or '0')
            if filled > 0 and not 0 < average <= number(order['limit_price']):
                raise PilotError('Invalid fill price for buy limit.')
            if status == 'rejected' and filled != 0:
                raise PilotError('Rejected order reports fills; manual review required.')
            if state['status'] in TERMINAL and state['observations'] and str(average) != state['observations'][-1]['filled_avg_price']:
                raise PilotError('Terminal fill price changed; manual review required.')
            observation = {'status': status, 'filled_qty': str(filled), 'filled_avg_price': str(average)}
            if not state['observations'] or state['observations'][-1] != observation:
                state['observations'].append(observation)
            state.update(status=status, filled_qty=str(filled))
            self._write(path, state)
            return state
        return self._mutate(write)
