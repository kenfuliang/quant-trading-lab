"""Bounded Alpaca PAPER transport and checks. No configurable trading host."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from research.alpaca_pilot import NoRedirect, credentials

PAPER = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
MAX_NOTIONAL = Decimal("1000")


class PaperError(RuntimeError):
    pass


class AlpacaPaperHTTP:
    def __init__(self, env_file=".env.alpaca", root=None):
        self.auth = credentials(env_file)
        self.root = Path(root) if root else None
        self.calls = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, path, body=None, *, data=False):
        allowed_get = {"/v2/clock", "/v2/account", "/v2/positions", "/v2/orders", "/v2/assets/SPY", "/v2/calendar", "/v2/orders:by_client_order_id"}
        route = path.split("?", 1)[0]
        if data:
            permitted = method == "GET" and route in {"/v2/stocks/SPY/bars", "/v2/stocks/SPY/quotes/latest"}
        else:
            permitted = ((method == "GET" and route in allowed_get) or
                         (method == "POST" and route == "/v2/orders") or
                         (method == "DELETE" and route.startswith("/v2/orders/") and len(route.split("/")) == 4))
        if not permitted or not path.startswith("/v2/") or "://" in path:
            raise PaperError("Route outside bounded SPY paper integration.")
        if method == "POST":
            validate_order(body or {}, Decimal(0) if (body or {}).get("side") == "buy" else Decimal(1))
        if self.calls >= 120:
            raise PaperError("Paper session HTTP budget exhausted.")
        self.calls += 1
        req = urllib.request.Request((DATA if data else PAPER) + path,
            data=json.dumps(body).encode() if body is not None else None, method=method,
            headers={"APCA-API-KEY-ID": self.auth[0], "APCA-API-SECRET-KEY": self.auth[1],
                     "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=10) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise PaperError("Paper response exceeds size limit.")
                if self.root:
                    self.root.mkdir(parents=True, exist_ok=True)
                    (self.root / f"http-{self.calls:03d}.json").write_bytes(raw)
                return json.loads(raw) if raw else None
        except Exception as e:
            code = e.code if isinstance(e, urllib.error.HTTPError) else None
            raise PaperError(f"Paper HTTP {method} failed ({code or type(e).__name__}); no retry.") from None

    def preflight(self):
        clock = self.request("GET", "/v2/clock")
        account = self.request("GET", "/v2/account")
        positions = self.request("GET", "/v2/positions")
        orders = self.request("GET", "/v2/orders?status=open&limit=100")
        asset = self.request("GET", "/v2/assets/SPY")
        if account.get("status") != "ACTIVE" or account.get("currency") != "USD" or any(account.get(k) is not False for k in ("trading_blocked", "account_blocked")):
            raise PaperError("Paper account is not eligible for this USD test.")
        if positions or orders:
            raise PaperError("Bounded test requires a flat account with no open orders; existing state untouched.")
        if asset.get("symbol") != "SPY" or not asset.get("tradable") or asset.get("status") != "active":
            raise PaperError("SPY is not tradable.")
        return {"clock": clock, "cash": account["cash"], "flat": True}

    def by_client_id(self, client_id):
        return self.request("GET", "/v2/orders:by_client_order_id?" + urllib.parse.urlencode({"client_order_id": client_id}))


def check_quote(quote, now_ns):
    ts = datetime.fromisoformat(quote["t"].replace("Z", "+00:00"))
    if ts.tzinfo is None:
        raise PaperError("Quote timestamp has no timezone.")
    age = now_ns / 1e9 - ts.timestamp()
    bid, ask = Decimal(str(quote["bp"])), Decimal(str(quote["ap"]))
    if not (bid.is_finite() and ask.is_finite()) or not 0 < bid <= ask <= MAX_NOTIONAL or not 0 <= age <= 10:
        raise PaperError("Quote is stale, crossed, invalid or exceeds test budget.")
    if (ask - bid) / ask > Decimal("0.01"):
        raise PaperError("Quote spread exceeds one percent.")
    return bid, ask, int(ts.timestamp() * 1e9)


def validate_order(body, position):
    try:
        price, qty = Decimal(body["limit_price"]), Decimal(body["qty"])
    except Exception:
        raise PaperError("Malformed paper order.") from None
    if body.get("symbol") != "SPY" or body.get("type") != "limit" or body.get("time_in_force") != "day" or body.get("extended_hours") is not False:
        raise PaperError("Only regular-hours SPY DAY limit orders are allowed.")
    if not price.is_finite() or not 0 < price <= MAX_NOTIONAL or qty != 1:
        raise PaperError("Paper test is capped at one share and USD1000 per order.")
    if body.get("side") not in ("buy", "sell") or position not in (Decimal(0), Decimal(1)):
        raise PaperError("Unexpected side or position.")
    if (body["side"] == "buy" and position != 0) or (body["side"] == "sell" and position != 1):
        raise PaperError("No pyramiding, borrowing or short selling.")


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")
