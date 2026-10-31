"""Restricted synthetic oracle loader. Never imports or initializes a cloud algorithm.

The original strategy stays private. Only allowlisted decision methods are read
from a hash-pinned source. A fresh class receives invented indicator/history stubs.
This checks a pure-policy port, not real indicator, fill, data or account parity.
"""
import ast
import builtins
import copy
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import pandas as pd

METHODS={'_t11_ready','_t11_weights','_ungated_t11_weights','_t11_bond_baller','_t11_feaver_bear'}
CALLS={'all','len','history','items','values','get','_t11_bond_baller','_t11_feaver_bear','_ungated_t11_weights'}


def load_oracle(path,expected_sha256):
    path=Path(path);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Oracle source identity changed.')
    module=ast.parse(raw.decode());classes=[n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='QuadEnsemble']
    if len(classes)!=1:raise ValueError('Exactly one reference class required.')
    methods=[copy.deepcopy(n) for n in classes[0].body if isinstance(n,ast.FunctionDef) and n.name in METHODS]
    names=[n.name for n in methods]
    if not {'_t11_ready','_t11_weights','_t11_bond_baller','_t11_feaver_bear'}<=set(names) or len(names)!=len(set(names)):raise ValueError('Missing/duplicate reference method.')
    for method in methods:
        if any(not isinstance(n,ast.Name) or n.id!='property' for n in method.decorator_list):raise ValueError('Unapproved decorator.')
        for node in ast.walk(method):
            if isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.With,ast.AsyncWith,ast.Lambda,ast.ClassDef,ast.Await,ast.Yield)):raise ValueError('Unsafe reference node.')
            if isinstance(node,ast.Name) and node.id.startswith('__'):raise ValueError('Dunder reference forbidden.')
            if isinstance(node,ast.Attribute) and node.attr.startswith('__'):raise ValueError('Dunder attribute forbidden.')
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else None
                if name not in CALLS:raise ValueError('Non-policy call forbidden: '+str(name))
    cls=ast.ClassDef(name='PolicyOracle',bases=[],keywords=[],body=methods,decorator_list=[])
    tree=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]))
    env={'__name__':'synthetic_policy_oracle','__builtins__':{'all':all,'len':len,'property':property,'str':str,'dict':dict,'bool':bool,'__build_class__':builtins.__build_class__},'Resolution':NS(DAILY='invented_daily')}
    exec(compile(tree,'<hash-pinned synthetic oracle>','exec'),env)
    return env['PolicyOracle']


def evaluate(oracle_type,features,cap=1.):
    obj=oracle_type();obj.QUARTER=1.;obj._T11_LATE={'KMLM'};obj.is_warming_up=not features['core_ready']
    def indicator(value,ready=True):return NS(current=NS(value=float(value)),is_ready=bool(ready))
    obj._t11_rsi10={s:indicator(v,features['kmlm_ready'] if s=='KMLM' else features['core_ready']) for s,v in features['rsi10'].items()}
    obj._t11_rsi20={s:indicator(v,features['core_ready']) for s,v in features['rsi20'].items()}
    obj._t11_rsi60_sh=indicator(features['rsi60_sh'],features['core_ready'])
    obj._t11_spy_sma200=indicator(features['sma200_spy'],features['core_ready'])
    obj._t11_tqqq_sma20=indicator(features['sma20_tqqq'],features['core_ready'])
    obj._t11_kmlm_sma20=indicator(features['sma20_kmlm'],features['kmlm_ready'])
    symbols=set(features['prices'])|set(features['rsi10'])|{'UVXY','BIL','BTAL','SPXL','TECL','SOXL','TECS','SOXS','SQQQ','QLD'}
    obj._syms={s:s for s in symbols};obj.securities={s:NS(close=float(features['prices'].get(s,100))) for s in symbols}
    history=pd.DataFrame({'close':features['qqq_history']})
    obj.history=lambda symbol,count,resolution:history
    obj._gate=NS(cap=float(cap))
    return obj._t11_weights()
