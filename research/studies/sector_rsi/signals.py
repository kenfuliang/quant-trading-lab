"""Unfitted fixed-sector breadth regime; future E3-C2 must be frozen separately."""
import math
import pandas as pd

from research.sector_corporate_actions import SYMBOLS


def breadth_timeline(indexes):
    sectors=[s for s in SYMBOLS if s!='SPY']
    panel=pd.DataFrame({s:indexes[s] for s in sectors})
    if panel.index.has_duplicates or not panel.index.is_monotonic_increasing:
        raise ValueError('Breadth index must be ordered and unique')
    if not panel.map(lambda x:math.isfinite(x) and x>0).all().all():
        raise ValueError('Invalid economic return indexes')
    averages=panel.rolling(200,min_periods=200).mean()
    breadth=(panel>averages).mean(axis=1).where(averages.notna().all(axis=1))
    state='unassessed';red_count=green_count=0;rows=[]
    for day,value in breadth.items():
        if not math.isfinite(value):
            state='unassessed';red_count=green_count=0;provisional='unassessed'
        else:
            red=value<=.2;yellow=value<.6
            provisional='red' if red else 'yellow' if yellow else 'green'
            if state=='unassessed':state='yellow'
            if red:state='red';red_count=green_count=0
            elif state=='red':
                red_count=red_count+1 if value>=.4 else 0;green_count=0
                if red_count>=5:state='yellow';red_count=0
            else:
                if state=='green' and yellow:state='yellow';green_count=0
                if state=='yellow':
                    green_count=green_count+1 if value>=.7 else 0
                    if green_count>=5:state='green';green_count=0
        rows.append({'breadth':value,'state':state,'provisional':provisional,
                     'red_count':red_count,'green_count':green_count,
                     'cap':{'unassessed':0.,'red':0.,'yellow':.5,'green':1.}[state],
                     'decision_close':str(day.date())})
    return pd.DataFrame(rows,index=panel.index).shift(1)
