# Preserved upstream CAPM source

`capm_framework_original.py` is an unchanged copy of
[QuantConnect/Lean at22404ea28b8d3f3c9eb74d6ed9f0444426f8e417](https://github.com/QuantConnect/Lean/blob/22404ea28b8d3f3c9eb74d6ed9f0444426f8e417/Algorithm.Python/CapmAlphaRankingFrameworkAlgorithm.py),
Apache-2.0. Its copyright/header and accompanying license are preserved. This
tracked fixture makes offline source-integrity tests independent of ignored local
exports. It is not executed by CI; it requires QuantConnect's hosted/runtime data.

The derivative generator is `../capm_study.py`. Its common test context, probe,
metrics and accounting changes are recorded in the frozen study and follow-up
receipt. Do not overwrite this upstream copy with a modified strategy.

## Preserved G-Score source

`g_score_legacy_original.py` is the unchanged single file from
[santoshlite/StrategyLibraryQC at6b406477afce2a12724dbf1031a99fbc1e1fee4d](https://github.com/santoshlite/StrategyLibraryQC/blob/6b406477afce2a12724dbf1031a99fbc1e1fee4d/G-Score%20Investing.py).
Its own QuantConnect Apache-2.0 header supplies the grant; no repository-wide
grant is inferred. `LICENSE-QuantConnect.txt` supplies the accompanying license.
SHA256: `a3958ecc57127d1b50ee9e97257d7c79381195bde3e64912f601fdc53be32d1c`.
The research generator parses its selector without importing/executing the original
ObjectStore/pickle code. Adaptations and exact-source limits are in the
[G-Score receipt](../../../docs/tasks/2026-10-26-gscore-spy-comparison.md).

## Preserved Dual Thrust example

`dual_thrust_fx_original.py` and `LICENSE-JeSuisTM.txt` preserve unchanged bytes from
[je-suis-tm/quant-trading at611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5](https://github.com/je-suis-tm/quant-trading/blob/611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5/Dual%20Thrust%20backtest.py).
The original is never imported/executed. Its current-session range look-ahead,
FX/session differences and the separately named causal SPY adaptation are recorded
in the [fallback receipt](../../../docs/tasks/2026-10-26-dual-thrust-spy-comparison.md).


## Preserved stock-pairs example

`stock_pairs_original.py` preserves unchanged bytes from
[je-suis-tm/quant-trading at611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5](https://github.com/je-suis-tm/quant-trading/blob/611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5/Pair%20trading%20backtest.py).
`LICENSE-JeSuisTM.txt` supplies the repository's Apache-2.0 license. The original
is never imported/executed. Future-aware sizing and material timing/statistical
repairs are recorded in the [pairs receipt](../../../docs/tasks/2026-10-26-stock-pairs-spy-comparison.md).
