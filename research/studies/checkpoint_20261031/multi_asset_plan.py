"""Non-executable ten-case design and explicit readiness gate for this epoch."""
SYMBOLS = ['SPY', 'IEF', 'GLD']
RULES = ['spy_entry_only', 'frozen_spy_gate', 'static_equal', 'trend_equal', 'relative_strength']
CASES = [dict(id=f'{cost}bp_{rule}', rule=rule, cost_bps=cost) for cost in (5, 25) for rule in RULES]
REQUIRED_GATES = ('intended_use_rights', 'raw_price_and_action_semantics_qualified',
                  'action_completeness_verified', 'historical_dividend_payment_dates_complete',
                  'exchange_calendar_and_availability_qualified', 'native_corporate_actions_configured',
                  'monthly_signals_synthetic_tests_passed', 'cash_allocator_native_synthetic_probe_passed',
                  'historical_runner_and_continuous_nav_verified')


def require_ready(receipt):
    gates = receipt.get('remaining_gates', {})
    if set(gates) != set(REQUIRED_GATES):
        raise ValueError('Incomplete/unknown readiness gate schema.')
    failed = [name for name in REQUIRED_GATES if gates[name] is not True]
    if failed:
        raise ValueError('Historical launch blocked: ' + ', '.join(failed))
    # Checking qualifications neither grants financial budget nor starts a run.
    return {'qualification_checks_passed': True, 'execution_started': False}
