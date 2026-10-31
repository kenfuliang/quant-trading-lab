"""Reassemble DOM-visible summary fragments, requiring all parts and SHA256 identity."""
import hashlib,json,sys
from pathlib import Path

def decode(texts,case):
    groups={}
    for text in texts:
        if 'QCA|' not in text:continue
        marker=text[text.index('QCA|'):]
        _,c,seq,index,total,digest,chunk=marker.split('|',6)
        if c!=case:continue
        key=(int(seq),int(total),digest);parts=groups.setdefault(key,{})
        i=int(index)
        if i in parts and parts[i]!=chunk:raise ValueError('Conflicting fragment')
        parts[i]=chunk
    if not groups:raise ValueError('No fragments')
    out=[]
    for (seq,total,digest),parts in sorted(groups.items()):
        if set(parts)!=set(range(total)):raise ValueError('Missing fragment')
        line=''.join(parts[i] for i in range(total))
        if hashlib.sha256(line.encode()).hexdigest()[:12]!=digest:raise ValueError('Digest mismatch/truncated fragment')
        payload=json.loads(line)
        if payload.get('case')!=case or payload.get('study')!='qc-breadth-v1':raise ValueError('Identity mismatch')
        out.append(line)
    return out
if __name__=='__main__':
    case=sys.argv[1];root=Path(__file__).resolve().parents[1]/'.local/qc-breadth-v1'
    rows=decode(json.loads((root/f'{case}-terminal-fragments.json').read_text()),case)
    (root/f'{case}-summary-cells.json').write_text(json.dumps(rows,indent=2)+'\n');print(case,len(rows),'complete checksummed summary records')
