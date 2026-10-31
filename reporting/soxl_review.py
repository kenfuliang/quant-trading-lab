"""Read-only extraction of visible QC summaries; never a daily-path audit."""
import re


def number(text, key):
    # A delimiter is mandatory: a display-truncated number is not a measurement.
    m = re.search(r'"'+re.escape(key)+r'":(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?=[,}])', text)
    return float(m[1]) if m else None


def observed_case(ax, case, run_id):
    marker = 'container result-tab-statistics-'+run_id
    start = ax.find(marker)
    if start < 0:
        raise ValueError('Wrong/missing visible run statistics')
    native = ax[start:].split('Rolling Statistics')[0]
    texts = re.findall(r'^\s*\d+ text (.*)$', native, re.M)
    fields = {}
    for label in ('Compounding Annual Return', 'Drawdown', 'Sharpe Ratio', 'End Equity', 'Total Orders', 'Total Fees'):
        if label not in texts:
            raise ValueError('Missing native field: '+label)
        value = texts[texts.index(label)+1].replace('%', '').replace('$', '').replace(',', '')
        fields[label] = float(value)
    fields['derived_calmar_from_rounded_native_statistics'] = (fields['Compounding Annual Return']/fields['Drawdown'] if fields['Drawdown'] else None)
    messages = {}
    for line in ax.splitlines():
        m = re.search(r'QCA\|'+re.escape(case)+r'\|(\d+)\|(\d+)\|\d+\|[a-f0-9]{12}\|(.*)$', line)
        if m:
            key = (int(m[1]), int(m[2]))
            if key in messages and messages[key] != m[3]:
                raise ValueError('Conflicting observed fragment')
            messages[key] = m[3]
    annual = []
    for seq in range(1,7):
        text = messages.get((seq,0),'')
        ret, dd = number(text,'ret'), number(text,'dd')
        if ret is not None and dd is not None:
            annual.append(dict(year=2019+seq, return_pct=ret*100, drawdown_pct=abs(dd)*100,
                               sharpe=number(text,'sharpe'), annual_calmar=ret/abs(dd) if dd else None))
    full = ' '.join(text for (seq,_),text in sorted(messages.items()) if seq == 7)
    cagr, dd = number(full,'cagr'), number(full,'dd')
    custom = {'cagr':cagr,'drawdown':dd,'derived_calmar':cagr/abs(dd) if cagr is not None and dd else None,
              'legacy_longest_underwater_sessions':number(full,'longest_uw'),
              'legacy_longest_underwater_calendar_days':number(full,'longest_uw_days')}
    return dict(case=case,run_id=run_id,evidence_status='provisional_visible_summary_not_export_audited',
                native=fields,custom_partial=custom,annual_partial=annual,
                official_export_verified=False,daily_equity_verified=False,
                original_daily_parity=False,order_ledger_reconciled=False)
