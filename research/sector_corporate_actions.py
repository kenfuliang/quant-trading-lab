"""Issuer-primary sector actions and an explicit offline cash/receivable ledger.

No native position mutations, network, strategy fitting or historical simulation.
Noncash XLF warmup event is typed separately; holding it in an account is rejected.
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

D=lambda x:Decimal(str(x))
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SYMBOLS=('XLB','XLE','XLF','XLI','XLK','XLP','XLRE','XLU','XLV','XLY','SPY')
IN_KIND_DATE='2016-09-19'


def workbook_actions(path, *, start='2016-01-01', end='2025-12-31'):
    """Preserve row/source metadata; sum cash components except the typed XLF event."""
    with zipfile.ZipFile(path) as z:
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    actions=[];excluded=[];seen=set();identities={};header=False
    for row in sheet.findall('.//s:sheetData/s:row',NS):
        vals={}
        for c in row.findall('s:c',NS):
            v=c.find('s:v',NS);text=v.text if v is not None else ''
            if c.get('t')=='s' and text:text=strings[int(text)]
            vals[''.join(x for x in c.get('r') if x.isalpha())]=text
        if vals.get('B')=='TICKER':
            header=all(vals.get(k)==v for k,v in {'C':'CUSIP','D':'EX-DATE','F':'PAYABLE DATE','G':'DIVIDEND ($)','H':'SHORT TERM CAPITAL GAIN ($)','I':'LONG TERM CAPITAL GAIN ($)'}.items())
            continue
        if vals.get('B') not in SYMBOLS:continue
        if not header:raise ValueError('Issuer workbook schema/header mismatch.')
        symbol=vals['B'];cusip=vals.get('C','')
        if not re.fullmatch(r'[A-Z0-9]{9}',cusip):raise ValueError('Missing issuer identity.')
        if symbol in identities and identities[symbol]!=cusip:raise ValueError('Ambiguous issuer identity.')
        identities[symbol]=cusip
        ex=datetime.strptime(vals['D'],'%m/%d/%Y').date().isoformat()
        pay=datetime.strptime(vals['F'],'%m/%d/%Y').date().isoformat()
        if not start<=ex<=end:continue
        if pay<ex:raise ValueError('Payment before ex-date.')
        amount=sum((D(vals.get(k,'').strip() or '0') for k in ('G','H','I')),D(0))
        if not amount.is_finite() or amount<0:raise ValueError('Invalid distribution amount.')
        if amount==0:
            excluded.append({'symbol':symbol,'ex_date':ex,'pay_date':pay,'source_row':row.get('r'),'reason':'issuer_explicit_zero_distribution','amount':'0'})
            continue
        key=symbol+'-'+ex
        if key in seen:raise ValueError('Duplicate issuer distribution.')
        seen.add(key)
        action={'id':key,'symbol':symbol,'kind':'cash','ex_date':ex,'pay_date':pay,
                'amount':str(amount),'cusip':cusip,'source_row':row.get('r'),
                'components':{k:vals.get(k,'').strip() for k in ('G','H','I')}}
        if symbol=='XLF' and ex==IN_KIND_DATE:
            if amount!=D('.139146'):raise ValueError('Unexpected XLF share distribution ratio.')
            action.update(kind='in_kind',child_symbol='XLRE',ratio=str(amount))
            del action['amount']
        actions.append(action)
    if set(identities)!=set(SYMBOLS) or len(set(identities.values()))!=len(SYMBOLS):raise ValueError('Missing/ambiguous issuer symbols.')
    return sorted(actions,key=lambda x:(x['ex_date'],x['symbol'])),identities,excluded


def normalize_splits(pages, issuer_reviews):
    """Require explicit independent issuer form review for every provider split."""
    result=[];keys=set()
    for page in pages:
        for row in page['corporate_actions'].get('forward_splits',[]):
            s=row['symbol'];ex=row['ex_date'];ratio=D(row['new_rate'])/D(row['old_rate'])
            review=issuer_reviews.get(s)
            if not review or review['ex_date']!=ex or D(review['ratio'])!=ratio or not review['source_sha256']:
                raise ValueError('Split issuer review missing or inconsistent.')
            if (s,ex) in keys:raise ValueError('Duplicate split.')
            keys.add((s,ex));result.append({'id':s+'-split-'+ex,'symbol':s,'kind':'split',
                'ex_date':ex,'ratio':str(ratio),'source_sha256':review['source_sha256']})
    if {r['symbol'] for r in result}!=set(issuer_reviews):raise ValueError('Incomplete split set.')
    return result


def total_return_indexes(frames, actions):
    """Prefix-causal economic return features; raw executable prices stay separate."""
    import pandas as pd
    index=frames['SPY'].index
    if index.empty or index.has_duplicates or not index.is_monotonic_increasing:raise ValueError('Invalid session index.')
    if any(not f.index.equals(index) for f in frames.values()):raise ValueError('Unaligned prices.')
    for frame in frames.values():
        if any(not D(x).is_finite() or D(x)<=0 for x in frame['close']):raise ValueError('Invalid raw close.')
    dated={}
    for a in actions:
        if a['ex_date']==index[0].strftime('%Y-%m-%d'):raise ValueError('Action on first close requires an earlier anchor.')
        dated.setdefault(a['ex_date'],[]).append(a)
    out={s:[D(100)] for s in frames}
    for i in range(1,len(index)):
        day=index[i].strftime('%Y-%m-%d')
        for s,frame in frames.items():
            same=[a for a in dated.get(day,[]) if a['symbol']==s]
            split=D(1);cash=D(0);in_kind=D(0)
            for a in same:
                if a['kind']=='split':split*=D(a['ratio'])
                elif a['kind']=='cash':cash+=D(a['amount'])
                elif a['kind']=='in_kind':
                    in_kind+=D(a['ratio'])*D(frames[a['child_symbol']].iloc[i]['close'])
                else:raise ValueError('Unknown action type.')
            if split!=1 and in_kind:raise ValueError('Concurrent split/in-kind unsupported.')
            before=D(frame.iloc[i-1]['close']);close=D(frame.iloc[i]['close'])
            factor=(split*(close+cash)+in_kind)/before
            if not factor.is_finite() or factor<=0:raise ValueError('Invalid economic return.')
            out[s].append(out[s][-1]*factor)
    return {s:pd.Series([float(x) for x in vals],index=index,name=s) for s,vals in out.items()}


class ActionLedger:
    """Research ledger: splits before open, payable cash at close, no cash advances.

    Payments already due before a session are available at that session's open.
    Same-day payments become spendable only after that session's close. A native
    engine/broker corporate-action handler is not implied by this project ledger.
    """
    def __init__(self, actions, *, capital='300000', symbols=SYMBOLS):
        self.symbols=tuple(symbols);self.cash=D(capital);self.shares={s:0 for s in symbols}
        self.actions=actions;self.receivables={};self.paid=set();self.events=[];self.last_day=None;self.last_close=None
        if not self.cash.is_finite() or self.cash<0:raise ValueError('Invalid capital.')
        ids=set(); action_keys=set()
        for a in actions:
            ex=date.fromisoformat(a['ex_date'])
            if a['id'] in ids or a['symbol'] not in self.shares:raise ValueError('Invalid/duplicate action identity.')
            ids.add(a['id'])
            key=(a['symbol'],a['kind'],a['ex_date'])
            if key in action_keys:raise ValueError('Duplicate symbol/type/date action.')
            action_keys.add(key)
            if a['kind']=='cash':
                if date.fromisoformat(a['pay_date'])<ex or not D(a['amount']).is_finite() or D(a['amount'])<=0:raise ValueError('Invalid cash action.')
            elif a['kind'] in ('split','in_kind'):
                if not D(a['ratio']).is_finite() or D(a['ratio'])<=0:raise ValueError('Invalid share ratio.')
            else:raise ValueError('Unsupported action kind.')

    @property
    def outstanding(self):return sum((x['amount'] for k,x in self.receivables.items() if k not in self.paid),D(0))

    def _pay(self, day, inclusive):
        for key,item in self.receivables.items():
            due=item['pay_date']<=day if inclusive else item['pay_date']<day
            if key not in self.paid and due:
                credit=item['amount'].quantize(D('.01'),rounding=ROUND_HALF_EVEN)
                self.cash+=credit;self.paid.add(key)
                self.events.append({'kind':'payment','id':key,'date':day,'cash_credit':str(credit),'rounding_pnl':str(credit-item['amount'])})

    def before_open(self,day):
        date.fromisoformat(day)
        if day==self.last_day:return
        if self.last_day and day<self.last_day:raise ValueError('Time moved backwards.')
        if self.last_day and self.last_close!=self.last_day:raise ValueError('Prior close not finalized.')
        same=[a for a in self.actions if a['ex_date']==day]
        # Preflight every quantity-changing action before any state mutation.
        proposed=dict(self.shares)
        for a in same:
            s=a['symbol']
            if a['kind']=='split':
                new=D(proposed[s])*D(a['ratio'])
                if new!=new.to_integral_value():raise ValueError('Fractional split entitlement unsupported.')
                proposed[s]=int(new)
            elif a['kind']=='in_kind' and proposed[s]:raise ValueError('Held in-kind action unsupported; warmup must remain flat.')
        self._pay(day,False)
        for a in same:
            s=a['symbol']
            if a['kind']=='split':
                old=self.shares[s];self.shares[s]=proposed[s]
                self.events.append({'kind':'split','id':a['id'],'date':day,'old_shares':old,'new_shares':self.shares[s]})
        for a in same:
            if a['kind']=='cash':
                amount=D(self.shares[a['symbol']])*D(a['amount'])
                self.receivables[a['id']]={'amount':amount,'pay_date':a['pay_date']}
                self.events.append({'kind':'entitlement','id':a['id'],'date':day,'shares':self.shares[a['symbol']],'amount':str(amount)})
        self.last_day=day

    def fill(self,symbol,quantity,price,fee='1'):
        if self.last_day is None or self.last_close==self.last_day:raise ValueError('Fills require an open session.')
        if symbol not in self.shares or type(quantity) is not int or quantity==0:raise ValueError('Invalid whole-share fill.')
        price=D(price);fee=D(fee)
        if not price.is_finite() or price<=0 or not fee.is_finite() or fee<0:raise ValueError('Invalid fill economics.')
        after=self.cash-D(quantity)*price-fee
        if after<0 or self.shares[symbol]+quantity<0:raise ValueError('Borrowing or shorting forbidden.')
        self.cash=after;self.shares[symbol]+=quantity

    def close(self,day,marks):
        if day!=self.last_day:raise ValueError('Close requires matching open.')
        if set(marks)!=set(self.shares) or any(not D(p).is_finite() or D(p)<=0 for p in marks.values()):raise ValueError('Missing/invalid mark.')
        self._pay(day,True);self.last_close=day
        return self.cash+self.outstanding+sum((D(self.shares[s])*D(marks[s]) for s in self.shares),D(0))
