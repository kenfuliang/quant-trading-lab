"""One declared reporting-only amendment; no strategy/order/accounting edits."""
import ast,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'.local/qc504-ablation-v1'
EMIT='''def _audit_emit(self,payload):
    if payload.get('kind')=='selections':
        return
    if payload.get('kind')=='assets':
        payload=dict(payload,values=[])
    line=json.dumps(payload,separators=(',',':'),allow_nan=False)
    digest=hashlib.sha256(line.encode()).hexdigest()[:12]
    self._audit_message_sequence=getattr(self,'_audit_message_sequence',0)+1
    chunks=[line[i:i+145] for i in range(0,len(line),145)]
    for i,chunk in enumerate(chunks):
        message='QCA|%s|%s|%s|%s|%s|%s'%(AUDIT_CASE,self._audit_message_sequence,i,len(chunks),digest,chunk)
        self._audit_log_bytes+=len(message)+60
        if self._audit_log_bytes>9300:raise ValueError('Declared summary log budget exceeded')
        self.debug(message)
'''
def repair():
    planfile=ROOT/'research/plans/qc504-ablation-v1.json';old=json.loads(planfile.read_text());new=dict(old)
    new.update(revision=2,max_financial_attempts=7,technical_repair_slots=2,amended_utc=datetime.now(timezone.utc).isoformat(),amendment='Two native-complete cases have inaccessible log tables and truncated terminal JSON. Fragment reporting at145 chars with checksum; omit asset lists/selection counts, retain P&L residual. Two reporting-only reruns; no financial policy change; same original deadline. Preserve frozen v1 and all attempts.')
    (ROOT/'research/plans/qc504-ablation-v1.frozen.json').write_text(json.dumps(old,indent=2)+'\n')
    for case in old['cases']:
        p=RAW/f'{case}-source.py';source=p.read_text();(RAW/f'{case}-source-v1.py').write_text(source)
        tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef));original={n.name:ast.dump(n) for n in cls.body if isinstance(n,ast.FunctionDef)}
        for i,node in enumerate(cls.body):
            if isinstance(node,ast.FunctionDef) and node.name=='_audit_emit':cls.body[i]=ast.parse(EMIT).body[0]
        for n in cls.body:
            if isinstance(n,ast.FunctionDef) and n.name!='_audit_emit':assert original[n.name]==ast.dump(n)
        p.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n');new['source_hashes']=dict(new['source_hashes']);new['source_hashes'][case]=hashlib.sha256(p.read_bytes()).hexdigest()
    planfile.write_text(json.dumps(new,indent=2)+'\n')
    print('Reporting-only AST amendment frozen; cap7, same deadline.')
if __name__=='__main__':repair()
