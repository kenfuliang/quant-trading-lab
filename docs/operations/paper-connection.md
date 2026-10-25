---
status: active
updated: 2026-10-25
owner: project-maintainers
---

# IBKR paper observation SOP

This file owns broker connection procedure. [Root README](../../README.md)
owns current verification status. Run commands from the repository root.
Use this SOP when paper access is enabled and broker observation is requested.
The installed tools contain no execution client. Adding execution is M5 work,
with acceptance criteria in the [roadmap](../roadmap.md).

Prerequisites: user-managed Gateway login, paper access, local virtual environment,
and no other probe/observer using client IDs 71 or 72. Credentials are entered
directly into Gateway. Never infer a paper session from port number or UI alone:
the existing probe requires exclusively DU-prefixed account IDs.

## Establish the paper observation session

IB Gateway is installed at:

`/Users/kenfuliang/Applications/IB Gateway 10.50/IB Gateway 10.50.app`

Select **IB API** and **Paper Trading** and verify a red
**SIMULATED TRADING** banner. Enter your paper username/password directly in
Gateway and complete any two-factor or account terms prompt yourself.
Credentials are not needed in this workspace.

The 2026-10-24 login attempt reported: "This account does not have paper trading access enabled."
Check Client Portal → User menu → Settings → Account Configuration → Paper
Trading Account. Verify the paper username/account shown there and use those
paper credentials in Gateway. If paper access is not provisioned, request it in
Client Portal yourself. IBKR says new paper accounts are normally created within
24 hours under normal business circumstances. This workspace cannot resolve
account eligibility or provision the account. See:
https://www.ibkrguides.com/clientportal/papertradingaccount.htm

After login, open Configure → Settings → API → Settings:

- Set/verify the socket port is **4002**.
- Keep access restricted to the local machine (127.0.0.1).
- Keep **Read-Only API** enabled for this first connection check.
- If Gateway asks to approve the local API connection, review and approve it.

Do not disable order precautions or change live-account access for this setup.
The active starter has no execution client and no order-submission strategy.

## Verify locally

From this workspace:

```sh
.venv/bin/python scripts/paper.py doctor
.venv/bin/python scripts/paper.py probe
.venv/bin/python scripts/paper.py observe --seconds 45
```

`doctor` checks actual imports and builds the adapter configuration without
connecting. `probe` connects through the IB API, reads managed account IDs, and
rejects empty, mixed, or non-DU account lists. It does not print full account IDs
or request orders. It uses client ID 71 and disconnects afterward.

`observe` first repeats that identity check, then runs a NautilusTrader data-only
node using client ID 72. It resolves SPY.ARCA and subscribes to quote ticks, then
stops automatically. It reports data connection and instrument-loading status.
It requests delayed/frozen data so the initial test does not presume a paid
real-time market-data entitlement. Delayed/frozen quotes and a weekend session
are not evidence of real-time trading readiness. Market-data permission errors
must be resolved with the appropriate IBKR entitlements before strategy testing.

Keep Gateway open. Gateway sign-in, restarts, and required reauthentication are
managed by you. Run only one copy of each check to avoid client ID conflicts.
Use Ctrl+C to stop observation early. Stop if identity is rejected, connectivity fails, or feed permissions are missing.
These commands verify neither order handling nor quote freshness. Inspect quote
timestamps and feed type separately before claiming data readiness.

Logs can contain account information;
redirect them into ignored `.local/` if needed and do not publish them.

## Completion receipt

Record date, command exit status, engine version, verified account type/count
(without full account IDs), connection/instrument result, and feed observations.
A missing quote leaves quote receipt unverified even if instrument loading passes.
Keep raw logs in ignored `.local/`; link only redacted summaries from task records.
On failure, follow the [incident SOP](incidents.md). Restore a known stopped local
observer state; leave external orders untouched unless separately authorized.

## Source evidence

- NautilusTrader v1.231.0 source: `27a8e54e7ac3c57d6cbf8891f0283dfbaee97317`.
- LEAN engine inspected: `f3d841e60dfd010ee5fc293ea893e56952484108`.
- Official LEAN IB adapter inspected: `fb86123c7ea07c3e9d02d56ed7476675e3e4578a`.
  Its `Initialize` calls `ValidateSubscription`, which calls QuantConnect's
  `modules/license/read` endpoint. This component was not modified or run.
- An in-progress LEAN engine image download was canceled after the engine switch.
  Cloned source and earlier sample data remain ignored for historical reference.
- The original IB Gateway installer was retained under ignored `.local/installers/`
  during setup; installer files are not runtime dependencies.

Primary sources:

- https://github.com/nautechsystems/nautilus_trader/tree/v1.231.0
- https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/docs/integrations/ib.md
- https://www.interactivebrokers.com/en/trading/ibgateway-latest.php
- https://github.com/QuantConnect/Lean.Brokerages.InteractiveBrokers
