"""Three fixed financial cases after dated historical-sector qualification."""
def _risk_monthly(self, data):
    month=self._decision_month
    if month==self._risk_previous_month:return
    self._risk_previous_month=month
    for symbol in self._weights:
        detail=self._sector_details[symbol]
        if detail[-1][:10]>str(self.time.date()):raise ValueError('Future fundamental observation')
        code,source=resolved_sector(detail[1],detail[2],detail[3],
             sid=str(symbol.id),when=str(self.time.date()),fallbacks=SECTOR_FALLBACKS)
        self._risk_sectors[symbol]=code
        self._resolved_n+=int(source!='native_sector')
    limited=sector_weights(self._weights,self._risk_sectors)
    if CASE_MODE=='original':weights=dict(self._weights)
    elif CASE_MODE=='sector':weights=limited
    elif CASE_MODE=='matched':weights=matched_weights(self._weights,limited)
    else:raise ValueError('Unknown fixed case')
    self._risk_sector_weights=weights
    total=.9*sum(weights.values())
    self._target_hash.update(('%s:%.10f\n' % (str(self.time.date()),total)).encode())
    rows=[self._risk_index(s) for s in self._weights]
    self._risk_months.append([int(self.time.strftime('%Y%m%d')),
         ('unassessed','green','yellow','red').index(self._gate.state),self._ready_counts[-1],rows])
