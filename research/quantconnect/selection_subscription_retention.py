"""Keep unheld current/delayed targets subscribed through staged execution.
This changes subscription lifetime, not the historical feature universe or ranking.
"""
def retained_targets(self):
    return list(dict.fromkeys(self._selected+list(self._weights)+list(getattr(self,'_delay_weights',{}))))
