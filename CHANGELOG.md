# Changelog

## [0.2.1] — 2026-06-02

### Added
- `client.check_lock(instrument, injected_data=None)` — binary EXECUTE / VETO decision
  for wiring directly into an execution management system or order router. Calls
  `POST /v1/bridge/check-lock`. Returns `authorized` bool, `decision` string, and full
  forensics payload: failed lock name, VPIN toxicity, pip multiplier, VWAP deviation,
  estimated slippage, and suggested max clip size. Graceful `CONNECTION_ERROR` fallback
  matches the existing `verify_regime()` pattern.
- `SovereignClient` — alias for `DeepAlgoClient`. Both names import correctly:
  `from deepalgo_sovereign import SovereignClient`.

### Fixed
- `verify_regime()` response documentation corrected. Previous README showed
  `regime_label`, `lock1_pass`, `lock2_pass`, `lock3_pass` fields which do not exist
  in the API response. Correct fields are `is_favorable`, `veto_reason`,
  `stability_score`, `metrics.regime`, `metrics.composite_confidence`,
  `metrics.vpin_at_time`, `metrics.entropy_scalar`, and related `metrics.*` keys.

### Removed
- `validate_sequence()` — was calling `/v1/validate_sequence` which does not exist.
  `check_lock()` is the correct equivalent for EMS integration.

---

## [0.2.0] — 2026-05-31

### Added
- `DeepAlgoClient.enroll(email)` — self-registration classmethod. Provisions a free API key via `POST /register/free` and emails it within seconds. No account creation required.
- `client.get_entry_signal(instrument)` — OU-calibrated entry timing. Returns live OU z-score, quality band (HIGH/MEDIUM/LOW), optimal entry delay in candles, and best confirmation signal derived from 60-day IC analysis across 76 instruments.

### Changed
- `verify_regime()` timeout raised from 60s → 120s. Eliminates timeout errors on exotic crosses (XAG_JPY, XAU_JPY, commodity pairs) during peak sweep cycles.
- Package author updated to DeepAlgo Intelligence / support@deepalgo.co.uk.
- README rewritten with current API reference, tier table, and quick-start guide.

### Removed
- `python-dotenv` dependency — not required by the client.

---

## [0.1.2] — 2026-03-01

- Initial public release with `verify_regime()` and `validate_sequence()`.
