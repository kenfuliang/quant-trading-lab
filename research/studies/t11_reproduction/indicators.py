"""Source-semantic indicator prototypes; native LEAN decimal parity is unverified.

Project implementation of Wilder/SMA formulas, inspected against the Apache-2.0
LEAN sources at vendor/Lean commit f3d841e60dfd010ee5fc293ea893e56952484108:
Indicators/{RelativeStrengthIndex,WilderMovingAverage,SimpleMovingAverage}.cs.
That checkout is not proven to match the saved18209 binary. Python Decimal28
arithmetic is not a substitute for an exact .NET decimal/engine comparison.
"""
from collections import deque
from decimal import Decimal,localcontext

D=lambda value:Decimal(str(value))


def value(x):
    result=D(x)
    if not result.is_finite() or result<=0:raise ValueError('Positive finite completed price required.')
    return result


class SimpleAverage:
    def __init__(self,period):
        if not isinstance(period,int) or period<1:raise ValueError('Positive integer period required.')
        self.period=period;self.window=deque(maxlen=period);self.samples=0;self.current=D(0)
    @property
    def ready(self):return self.samples>=self.period
    def update(self,close):
        x=value(close)
        with localcontext() as ctx:
            ctx.prec=28;self.window.append(x);self.samples+=1;self.current=sum(self.window,D(0))/len(self.window)
        return self.current


class WilderRSI:
    def __init__(self,period):
        if not isinstance(period,int) or period<1:raise ValueError('Positive integer period required.')
        self.period=period;self.previous=None;self.samples=0;self.differences=0
        self.gain=self.loss=self.gain_sum=self.loss_sum=D(0);self.current=D(100)
    @property
    def ready(self):return self.differences>=self.period
    def update(self,close):
        x=value(close)
        with localcontext() as ctx:
            ctx.prec=28
            if self.previous is not None:
                delta=x-self.previous;gain=max(delta,D(0));loss=max(-delta,D(0));self.differences+=1
                # The original WMA starts recursive updating when Samples==period;
                # its previous value is the SMA of period-1 differences.
                if self.differences<self.period:
                    self.gain_sum+=gain;self.loss_sum+=loss
                    self.gain=self.gain_sum/self.differences;self.loss=self.loss_sum/self.differences
                else:
                    k=D(1)/self.period;self.gain=gain*k+self.gain*(1-k);self.loss=loss*k+self.loss*(1-k)
            self.previous=x;self.samples+=1
            self.current=D(100) if self.loss.quantize(D('0.0000000001'))==0 else D(100)-D(100)/(1+self.gain/self.loss)
        return self.current
    def snapshot(self):
        return {'period':self.period,'samples':self.samples,'differences':self.differences,'previous':str(self.previous) if self.previous is not None else None,
            'gain':str(self.gain),'loss':str(self.loss),'gain_sum':str(self.gain_sum),'loss_sum':str(self.loss_sum),'current':str(self.current),'ready':self.ready,
            'native_engine_parity':False}
