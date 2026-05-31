# Changelog

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
