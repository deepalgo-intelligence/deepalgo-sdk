# Changelog

All notable changes to the `deepalgo-sovereign` Python SDK.

No `CHANGELOG.md` existed before this file — reconstructed 2026-11-17 by
diffing `DeepAlgoClient`'s real methods between the last published release
(0.2.0) and the current repo HEAD, not from commit messages alone, so this
is accurate rather than a restatement of intent. **0.2.1, 0.2.2 and 0.2.3
were bumped in `setup.py` but never actually published to PyPI** — the
installed package on PyPI today is still 0.2.0. This release (0.2.4) is
the real "what's new since the last thing anyone actually installed."

## [0.2.4] — 2026-11-17 (first publish since 0.2.0)

### Added
- `verify_regime()` / `check_lock()`: new optional `strategy_type` parameter
  (`"mean_reversion"` default, `"trend"` new). The default preserves exact
  prior behaviour for every existing caller. `"trend"` runs a different,
  deliberately lighter check matched to momentum/breakout entries — see the
  method's own docstring for exactly which signals run under each value.
  `"carry"`/`"divergence"` are planned, not yet available (the API returns
  422, not a silent fallback).
- `check_lock(instrument)` — fast binary EXECUTE/BLOCK decision, reading
  from pre-computed state rather than running the full gauntlet.
- `execute_and_track(...)` + `ExecutionResult` — combines a regime check
  with fill submission in one call; `ExecutionResult` exposes convenience
  properties (`is_favorable`, `verdict`, `veto_reason`, `regime`,
  `your_percentile`, `recommended_venue_next_time`, `potential_saving_pips`,
  `network_sample_size`) over the raw response dict.
- `get_fill_quality(instrument)` — execution-quality / adverse-selection
  advisory (VPIN-driven).
- `get_instrument_catalog()` — the real, live instrument universe by tier/
  asset class/volatility/toxicity bucket, replacing any hand-maintained list.
- `get_session_signal_quality(instrument)`.
- `get_decision(...)`, `get_decision_accuracy(...)`, `get_decision_breadth(...)`,
  `submit_decision_outcome(...)` — decision-framework endpoints.
- `submit_fill(...)` — client fill submission for the collective venue-
  intelligence network (feeds `recommended_venue`/`venue_quality_scores`
  in `get_fill_quality()`'s own response for every client on the platform).
- `deepalgo_sovereign.emsx` — Bloomberg EMSX pre-trade hook module.
- `SovereignClient` — alias for `DeepAlgoClient` (both names work;
  `__init__.py`, already present, carried forward unchanged).

### Removed (breaking, if anyone depended on it)
- `validate_sequence(asset, candles)` — called `POST /v1/validate_sequence`,
  an endpoint that does not exist anywhere in the current live API (checked
  directly against `deepalgo_api_4_1.py`). Removing it does not newly break
  any real integration — the endpoint was already gone, so every call to
  this method in the published 0.2.0 SDK has only ever been able to return
  its own `CONNECTION_ERROR` fallback dict, never a real result.

## [0.2.1]–[0.2.3] — never published

Bumped in `setup.py` during development but never pushed to PyPI. Their
real content (check_lock, the EMSX hook, docs fixes) is folded into 0.2.4
above rather than released separately, since nobody has ever installed
an intermediate version to diff against.

## [0.2.0] — published, currently installed from PyPI

`enroll()`, `get_entry_signal()`, `verify_regime()`, `validate_sequence()`
(see Removed above), updated branding.
