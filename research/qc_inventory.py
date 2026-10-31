"""Read-only catalog metadata parsing and explicit provisional family labels."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

class Node:
    def __init__(self,tag='',attrs=(),parent=None):
        self.tag=tag;self.attrs=dict(attrs);self.parent=parent;self.children=[]
    def text(self):
        return ' '.join(''.join(x.text() if isinstance(x,Node) else x for x in self.children).split())
    def walk(self):
        yield self
        for c in self.children:
            if isinstance(c,Node):yield from c.walk()

class Tree(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self,text):
        super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.feed(text)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs,self.stack[-1]);self.stack[-1].children.append(n)
        if tag not in self.VOID:self.stack.append(n)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:self.stack=self.stack[:i];break
    def handle_data(self,text):self.stack[-1].children.append(text)

def tutorial_index(html):
    rows={}
    for a in Tree(html).root.walk():
        href=a.attrs.get('href','')
        if a.tag!='a' or '/tutorials/strategy-library/' not in href:continue
        url=urljoin('https://www.quantconnect.com',href).split('#')[0].rstrip('/')
        p=a.parent
        while p and p.tag!='tr':p=p.parent
        rows[url]={'title':a.text(),'url':url,'description':p.text() if p else a.text()}
    return list(rows.values())

FAMILIES=[
 ('ensemble',r'ensemble|multi.model|multi.engine|dual.engine|multi.strategy|multi.sleeve|four.sleeve|stacking'),
 ('machine_learning',r'\bml\b|machine.learning|neural|\bcnn\b|\blstm\b|\bsvm\b|xgboost|gradient.boost|naive.bayes|reinforcement|random.forest|\bhmm\b|hidden.markov|\bpca\b|regression|autoencoder|transformer|wavelet|long.short.term.memory|path.signature|path.signture'),
 ('momentum',r'momentum|relative.?strength|cross.sectional|winner|loser|\brs\b'),
 ('trend',r'trend|breakout|donchian|moving.average|\bema\b|\bsma\b|ichimoku|supertrend|dual.thrust|macd|\badx\b|parabolic'),
 ('mean_reversion',r'dip.buy|mean.rever|reversion|reversal|reverting|pullback|bounce|rebound|oversold|overbought|bollinger|\brsi\b|stochastic|contrarian'),
 ('value_quality',r'asset.growth|\bvalue\b|valuation|quality|fundamental|accrual|book.to.market|price.earnings|\broa\b|\broe\b|profitab|\bg.score\b|fama.french|\bcapm\b|\bbeta\b|capitalization|\bsize\b|dividend|earnings.yield'),
 ('earnings_event',r'earnings|event|announcement|surprise|\bsue\b|senator|insider|buyback|\bipo\b|patent|merger|spinoff'),
 ('carry_term_structure',r'\bcarry\b|term.structure|contango|backwardation|roll.yield|risk.premi|premium.harvest|yield.harvest'),
 ('volatility',r'volatil|\bvix\b|variance|\bvrp\b'),
 ('options',r'option|\bleaps\b|\bputs\b|\bcalls\b|straddle|strangle|iron.condor|covered.call|put.spread|call.spread|\bgamma\b|\bvega\b|\b0dte\b'),
 ('relative_value',r'\bpairs?\b|arbitrage|relative.value|cointegration|copula|(?:wti|brent).*spread|calendar.spread|cross.exchange|cross.venue|dispersion|market.neutral'),
 ('allocation_rotation',r'rotation|rotat|allocat|risk.parity|portfolio|rebalanc|minimum.variance|kelly|risk.budget|equal.weight|paired.switch'),
 ('seasonality',r'seasonal|january|calendar|holiday|turn.of.(?:the.)?month|lunar|expiration.week|overnight|day.of.the.week|month.cycle|12.month.cycle'),
 ('macro_sentiment',r'\bmacro\b|sentiment|\bnews\b|economic|inflation|interest.rate|yield.curve|risk.on|risk.off|risk.regime|fear|regime|market.timing|barometer'),
 ('liquidity_microstructure',r'liquidity|market.mak|order.book|microstruct|order.flow|volume|vwap|twap'),
 ('passive_accumulation',r'\bdca\b|dollar.cost|buy.and.hold'),
 ('monitoring_framework',r'monitoring|reporting.framework|template|framework|data.collect|diagnostic|\bdemo\b|\btest\b')]

def classify(title,description='',basis='title'):
    text=title if basis=='title' else title+' '+description
    hits=[(f,m.group(0)) for f,pattern in FAMILIES if (m:=re.search(pattern,text,re.I))]
    # Multi-label taxonomy: risk overlays and model classes can coexist with an economic mechanism.
    families=[f for f,_ in hits] or ['unresolved']
    return {'families':families,'classification_basis':basis,'classification_confidence':'provisional','matched_terms':dict(hits),'economic_mechanism_verified':False,'duplicate_status':'not code-compared'}

def normalize_community(passes):
    records={};observations=0
    for pass_name,pages in passes.items():
        assert [p['page'] for p in pages]==list(range(1,109)),pass_name
        for page in pages:
            assert len(page['rows'])==5
            for row in page['rows']:
                observations+=1
                link=next(l for l in row['links'] if re.search(r'/strategies/\d+/?$',l['href']))
                sid=re.search(r'/strategies/(\d+)',link['href'])[1];cells=row['cells'];assert len(cells)==7
                r=records.setdefault(sid,{'id':'QC-C-'+sid,'upstream_id':sid,'source_kind':'community','title':link['title'],'url':'https://www.quantconnect.com/strategies/'+sid+'/','author':cells[1],'organization':cells[2],'observed_claims':[],'appearances':[]})
                if r['title']!=link['title']:raise ValueError('Title changed during snapshot')
                # Store raw strings with source-defined windows; absent values remain null.
                metrics=dict(zip(['oos_3m_return','oos_3m_sharpe','oos_1y_sharpe'],[None if x=='-' else x for x in cells[3:6]]))
                if metrics not in r['observed_claims']:r['observed_claims'].append(metrics)
                r['appearances'].append({'pass':pass_name,'page':page['page'],'captured_utc':page['captured_utc']})
    return sorted(records.values(),key=lambda r:int(r['upstream_id'])),observations

def tutorial_article_observed(receipt):
    """HTTP200 alone is insufficient: reject soft404 and missing article headings."""
    return receipt.get('status')==200 and bool(re.search(r'/research/\d+/',receipt.get('final_url',''))) and bool(receipt.get('headings'))
