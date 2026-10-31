"""Causal sector fallback and a target-exposure-matched allocation control.

Numeric hierarchy follows QC's published AssetClassificationHelper enums.
No current company labels, future realized exposure, or silent cash exclusion.
"""
VALID_SECTORS = frozenset((101,102,103,104,205,206,207,308,309,310,311))


def resolved_sector(primary, group, industry, security_sector=0, *, sid='', when=None, fallbacks=()):
    if primary in VALID_SECTORS:
        return primary, 'native_sector'
    if primary != 0:
        raise ValueError('Invalid primary classification')
    candidates=[]
    if group:
        code=group//100
        if code not in VALID_SECTORS or not 10000<=group<=99999:
            raise ValueError('Invalid historical industry group')
        candidates.append((code,'native_group'))
    if industry:
        code=industry//100000
        if code not in VALID_SECTORS or not 10000000<=industry<=99999999:
            raise ValueError('Invalid historical industry')
        candidates.append((code,'native_industry'))
    if security_sector:
        if security_sector not in VALID_SECTORS:raise ValueError('Invalid security-sector field')
        candidates.append((security_sector,'native_security'))
    if candidates:
        if len({code for code,_ in candidates})!=1:raise ValueError('Conflicting historical classifications')
        return candidates[0]
    applicable=[r for r in fallbacks if r['sid']==sid and when is not None and r['available_date']<str(when) and r['effective_from']<=str(when)<=r['effective_to']]
    if applicable:
        if len({r['sector'] for r in applicable})!=1:raise ValueError('Conflicting dated fallback')
        latest=max(applicable,key=lambda r:r['available_date'])
        if latest['sector'] not in VALID_SECTORS or not latest['source_id']:raise ValueError('Unqualified fallback')
        return latest['sector'],latest['source_id']
    raise ValueError('Unresolved historical sector: '+sid+' '+str(when))


def matched_weights(original, sector_limited):
    total=sum(original.values())
    target=sum(sector_limited.values())
    if total<=0 or target<0 or target>total+1e-12:
        raise ValueError('Invalid allocation budget')
    return {s:w*target/total for s,w in original.items()}
