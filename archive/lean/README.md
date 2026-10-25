> Superseded 2026-10-24. Historical preparation only. Active owner: ../../README.md.

# LEAN + Interactive Brokers paper starter

Status: prepared locally; no engine backtest or broker connection verified.
Verified setup date: 2026-10-24, America/Los_Angeles.
This README owns setup instructions and current validation status.

## Hosting choice is open

LEAN is an Apache-2.0 open-source engine and can run independently of the
QuantConnect hosted service and paid CLI. The cloud instructions below describe
an optional managed route, not a requirement to use LEAN. A direct engine build
plus the separate Interactive Brokers brokerage plugin and a user-managed IB
Gateway is the alternative to investigate before any subscription purchase.
Native ARM bundled Gateway limitations do not prove cloud hosting is required;
an external Gateway or compatible execution host needs separate validation.
The current helper only covers the optional managed route.

## Optional managed execution path

```text
Free QuantConnect web editor → historical backtest
                                       ↓ after paid deployment resources are enabled
Local project → QuantConnect Cloud LEAN → Interactive Brokers DU paper account
```

The free QuantConnect account supports browser-based historical backtesting.
It does not include LEAN CLI access or IBKR paper/live deployment.
The paid Researcher tier supports those features; cloud deployment also needs
an available live node. Check the complete subscription cost before upgrading.
No upgrade or purchase has been made by this setup.

The Mac is ARM64 with Colima. QuantConnect's ARM engine image omits IB Gateway,
so the bundled local Gateway path is not ready. Cloud is one alternative; a
self-hosted engine with an external Gateway has not yet been validated here.

## Start with the free account

1. Sign in at https://www.quantconnect.com/terminal/.
2. Review and accept current account terms yourself if prompted.
3. Create a Python project named IBPaperStarter.
4. Copy IBPaperStarter/main.py into its main.py file.
5. Add the project parameter `smoke-order` with value `true` for a historical
   one-share order smoke test. Keep it `false` to observe bars without orders.
6. Run a backtest and check for a first SPY bar, one historical share order,
   order events, and a completed result without runtime errors.

The short October 2013 date range matches the bundled local sample data. This
is a plumbing check, not a strategy evaluation or profitability claim.

## Connect IBKR paper after enabling paid resources

Use an existing IBKR paper account and its paper credentials. Choose Interactive
Brokers as the brokerage, not QuantConnect Paper Trading: we want IB's simulated
order processing. Confirm the target is your DU-prefixed paper account and mode
is paper before starting. Credentials belong in the official deployment wizard,
not chat, source files, command arguments, or Git.

On QuantConnect's website, deploy the project through the live deployment wizard
with `smoke-order=false` first. Observe the first SPY bar and broker connection.
Check market data entitlements and paper data sharing in IBKR Client Portal.
A delayed feed is not equivalent to a real-time execution test.

After observing successfully, stop that deployment, set `smoke-order=true`, and
redeploy to place at most one new one-share SPY market order in a session during
regular market hours. The algorithm checks broker-reported paper mode and DU
account before processing data. Missing details stop execution. Existing SPY
holdings or open SPY orders suppress the smoke order. It does not automatically
sell the share. Stopping the algorithm does not itself close positions or cancel
all broker orders; inspect the paper account afterward.

Use a dedicated paper account/session. Only one deployment should run at a time.
The starter is not a general risk manager and must be redesigned before any
real-money use. If you manually close the position and restart the smoke test,
it can place another simulated order.

Optional CLI path once paid access and account terms are ready:

```sh
python3 scripts/paper.py backtest
python3 scripts/paper.py observe
python3 scripts/paper.py smoke
```

The helper temporarily sets the project parameter, pushes the project, and uses
the official deployment wizard. It restores the local parameter afterward; the
cloud project retains the uploaded parameter. Set it explicitly before every
manual deployment. Initial configuration used an existing cached QuantConnect
login; confirm the intended organization before uploading this project.

## Current evidence

- LEAN CLI 1.0.225 and Docker 29.5.2 are present.
- Workspace initialized; sample data downloaded; starter project created.
- QuantConnect account query is blocked by current terms acceptance.
- User reports a free QuantConnect account and an existing IBKR paper account.
- Docker CLI uses Colima. Python Docker access works with the context socket
  supplied via DOCKER_HOST; no global Docker settings were changed.
- Local backtest did not execute: the LEAN engine image is absent.
- Python syntax checks passed for the starter and helper. Engine runtime and
  broker behavior are unverified.
- No QuantConnect Cloud project has been created or deployed by this setup.
- No IBKR credentials were requested by the tools, stored, or used.
- No paper or real-money orders have been placed.

## References

- https://www.quantconnect.com/pricing/
- https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/brokerages/interactive-brokers
- https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/getting-started
- https://www.quantconnect.com/docs/v2/lean-cli/key-concepts/troubleshooting
