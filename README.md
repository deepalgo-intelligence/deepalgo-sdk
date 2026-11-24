# DeepAlgo Sovereign SDK

Python client for the [DeepAlgo Sovereign](https://gateway.deepalgo.co.uk) AI Regime API — institutional-grade regime classification, entry signal quality, session-stratified causal signal quality, and order-flow intelligence across FX, metals, indices, and commodities.

## Installation

```bash
pip install deepalgo-sovereign
```

## Quick Start

> **Get your key in 30 seconds — no GitHub account or card required.**
>
> Run the one-liner below in Python and check your inbox. That's it.

### 1. Get a free API key

```python
from deepalgo_sovereign import DeepAlgoClient

DeepAlgoClient.enroll("you@email.com")
# ✓ Prints: "Done — check your inbox for your free API key and quick-start instructions."
# Your key (e.g. da_free_xxxxxxxxxxxx) arrives by email within ~5 seconds.
# Check spam if you don't see it within 30 seconds.
```

No account creation, no GitHub, no card. If you already enrolled, calling `enroll()` again
with the same address resends your existing key.

### 2. Check a regime

```python
client = DeepAlgoClient(api_key="your_key_here")

regime = client.verify_regime("EUR_USD")
print(regime["is_favorable"])                        # True
print(regime["veto_reason"])                         # None  (or a veto code)
print(regime["metrics"]["regime"])                   # "MEAN_REVERTING"
print(regime["metrics"]["composite_confidence"])     # 0.7843
print(regime["metrics"]["vpin_at_time"])             # 0.31
print(regime["stability_score"])                     # "82.4%"
```

### 3. Check session signal quality

```python
sq = client.get_session_signal_quality("EUR_USD")
print(sq["current_session"])     # "Asian"
print(sq["current_quality"])     # "SPURIOUS"
print(sq["current_multiplier"])  # 1.3

# Some instrument/session combinations carry mostly genuine, structural order-flow
# signal; others are dominated by macro noise that only looks like signal. The
# multiplier reflects that distinction automatically — you don't need to know which
# regime you're in to benefit from it.

# All three sessions at a glance:
for session, data in sq["sessions"].items():
    print(f"{session}: {data['quality']} ({data['ic_reduction_pct']:+.1f}% IC change)")
```

### 4. Check entry signal quality

```python
signal = client.get_entry_signal("EUR_USD")
print(signal)
# {
#   "entry_quality": "HIGH",
#   "current_ou_z": 1.42,
#   "ou_z_threshold": 0.75,
#   "recommended_delay_candles": 3,
#   "best_confirmation_signal": "rsi_divergence",
#   "calibrated": True
# }

if signal["entry_quality"] in ("HIGH", "MEDIUM"):
    regime = client.verify_regime("EUR_USD")
    if regime["is_favorable"]:
        # statistically sound entry — proceed
        pass
```

## API Reference

### `DeepAlgoClient.enroll(email)`

Class method. Registers for a free API key — no account creation required. Key is emailed within seconds.

```python
DeepAlgoClient.enroll("you@email.com")
```

### `client.verify_regime(asset, use_tlock=True)`

Returns the full AI regime verdict for an instrument. Makes a live data fetch and runs
the complete three-lock gauntlet — typically 2–8 seconds.

> **Production use**: call `check_lock()` instead. It reads from a pre-computed Redis
> cache (updated every 60 s) and responds in under 100 ms. Use `verify_regime()` for
> strategy development, instrument evaluation, and anywhere you want full regime metadata.

| Parameter | Type | Description |
|---|---|---|
| `asset` | str | OANDA instrument name, e.g. `"EUR_USD"`, `"XAU_USD"` |
| `use_tlock` | bool | Enable/disable the third validation layer (default: `True`) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `is_favorable` | bool | `True` if all three locks pass |
| `veto_reason` | str \| None | Gate that blocked — `REGIME_VETO`, `AI_PROXY_VETO`, `TRANSFORMER_VETO`, `ENTROPY_VETO`, or `None` |
| `stability_score` | str | Lock 2 neural stability as a percentile, e.g. `"82.4%"` |
| `divergence` | str | Divergence label — `"NONE"` when regime is clean |
| `metrics.regime` | str | Classified market state — e.g. `"MEAN_REVERTING"`, `"TRENDING"`, `"HIGH_VOL"` |
| `metrics.composite_confidence` | float | Combined confidence after all internal scalars applied |
| `metrics.entropy` | float | Shannon entropy of return distribution (0–1); higher means noisier price action |
| `metrics.vpin_at_time` | float | Order-flow toxicity reading at scan time (0–1); higher values indicate more adverse-selection risk |
| `metrics.entropy_scalar` | float | Confidence multiplier from entropy |
| `metrics.vpin_scalar` | float | Confidence multiplier from order-flow toxicity |
| `metrics.macro_z_score` | float | Deviation vs macro driver spread |
| `metrics.lock3_score` | float | Sequence-pattern validation score |

### `client.check_lock(instrument, injected_data=None)`

Binary EXECUTE / VETO decision. Use this in your order router immediately before placing a trade — reads pre-computed state from Redis so response is sub-millisecond on the server side.

```python
decision = client.check_lock("EUR_USD")
if decision["authorized"]:
    place_order()
```

| Field | Type | Description |
|---|---|---|
| `authorized` | bool | `True` = EXECUTE, `False` = BLOCK |
| `decision` | str | `"EXECUTE"` or `"BLOCK"` |
| `forensics.failed_lock` | str | Which gate blocked, or `"NONE"` |
| `forensics.vpin_toxicity` | float | Current order-flow toxicity reading (0–1); higher values indicate more adverse-selection risk |
| `forensics.pip_multiplier` | int | Correct pip factor for this instrument |
| `forensics.execution_intelligence.execution_benchmarks.vwap_deviation_bps` | float | Distance from VWAP in basis points |
| `forensics.execution_intelligence.capacity_metrics.suggested_max_clip_usd` | float | Max recommended trade size |

### `client.get_session_signal_quality(instrument)`

Returns the DML-calibrated session signal quality for an instrument. Based on a Double Machine Learning study across 32 G10 FX, metals, and bond instruments — identifies whether order flow imbalance carries structural predictive content in the current session, or whether it is predominantly spurious macro co-movement.

| Field | Type | Description |
|---|---|---|
| `current_session` | str | `"Asian"`, `"London"`, or `"NewYork"` |
| `current_quality` | str | `"STRUCTURAL"`, `"MIXED"`, `"SPURIOUS"`, or `"UNKNOWN"` |
| `current_multiplier` | float | Lock 3 threshold multiplier currently active (`1.0`, `1.1`, or `1.3`) |
| `sessions` | dict | Per-session breakdown: quality, multiplier, ic_reduction_pct, structural_ic |
| `last_calibrated` | str | Date of most recent DML calibration run |

**Multiplier guide:**

| Quality | Multiplier | Meaning |
|---|---|---|
| `STRUCTURAL` | 1.0× | OFI signal is genuine — standard threshold |
| `MIXED` | 1.1× | Partial spurious component — threshold raised 10% |
| `SPURIOUS` | 1.3× | Predominantly macro noise — threshold raised 30% |

**Methodology note:** session quality is derived from a Double Machine Learning causal study that separates genuine, structural order-flow predictability from confounded macro co-movement that merely resembles signal. The underlying research methodology and calibration are proprietary to DeepAlgo Sovereign / DeepAlgo Ltd. and are not published; the `sessions` field above is the actionable output a client needs.

### `client.get_entry_signal(instrument)`

Returns OU-calibrated entry timing quality. Derived from 60-day IC analysis across 76 instruments — identifies whether the current moment is a statistically optimal entry point, not just whether the regime is right.

| Field | Type | Description |
|---|---|---|
| `entry_quality` | str | `HIGH`, `MEDIUM`, `LOW`, or `NO_DATA` |
| `current_ou_z` | float | Live OU z-score — deviation from equilibrium in σ |
| `ou_z_threshold` | float | Calibrated threshold from IC analysis |
| `recommended_delay_candles` | int | Optimal M5 candle wait after signal touch |
| `best_confirmation_signal` | str | Highest-IC confirmation signal at optimal lag |
| `calibrated` | bool | `False` if instrument has no calibration data yet |

### `client.get_instrument_catalog(tier="", asset_class="", include_live_toxicity=True)`

Browse the instrument catalog: every instrument Sovereign covers, which tier unlocks it, its full name alongside the exact code used by every other endpoint, a relative volatility bucket, typical spread, and (optionally) its current live VPIN toxicity tier. Available at every tier, including Free — use it to see what unlocks at the next tier up before deciding to upgrade.

```python
cat = client.get_instrument_catalog(tier="INSTITUTIONAL", asset_class="FX")
for row in cat["instruments"]:
    print(row["short_name"], row["full_name"], row["vol_bucket"], row["current_toxicity_tier"])
```

| Field | Type | Description |
|---|---|---|
| `short_name` | str | Exact code every other Sovereign endpoint uses (e.g. `EUR_USD`) — not a separate "generic" symbology, so it can be passed straight into `verify_regime()` / `get_fill_quality()` / `get_entry_signal()` unchanged |
| `full_name` | str | Human-readable name, e.g. `"Euro / US Dollar"` |
| `asset_class` | str | `FX`, `INDICES`, `BONDS`, `COMMODITIES`, or `METALS` |
| `min_tier` | str | Lowest tier that unlocks this instrument |
| `available_to_you` | bool | Whether your own key can query it today |
| `vol_bucket` | str \| None | `LOW`/`MEDIUM`/`HIGH`/`EXTREME` — a RELATIVE percentile rank within the full universe, not an absolute cutoff |
| `avg_spread_pips` | float \| None | Typical quoted spread |
| `current_toxicity_tier` | str \| None | Lightweight live VPIN read (`OPTIMAL`/`ACCEPTABLE`/`DEGRADED`/`HOSTILE`) — for an execution decision on one specific instrument, use `get_fill_quality()` instead, which layers in regime/AR1/RV on top of VPIN |

**Why the short_name is the OANDA code, not a separate symbology:** Sovereign's broker-agnostic positioning is about execution routing (no financial stake in where an order fills) — it is not about the instrument identifier format. Every endpoint in this SDK already takes and returns instrument codes in this same form; introducing a second convention here would mean translating it back before calling anything else, for no real benefit.

### `client.validate_sequence(asset, candles)`

Runs the full validation stack using 60 M5 candles of OHLCV data.

```python
result = client.validate_sequence("EUR_USD", candles=[...])  # list of 60 OHLCV dicts
# {"is_authorized": True, "verdict": "AUTHORIZED"}
```

## Supported Instruments

The API covers 76 real instruments across five asset classes (FX, Metals, Indices, Commodities, Bonds). The exhaustive, always-current list per tier — full name, short code, asset class, volatility bucket, typical spread — is available directly from `client.get_instrument_catalog()` rather than a static list here, which would drift:

- **FX** (29): EUR_USD, GBP_USD, USD_JPY, EUR_JPY, GBP_JPY, AUD_USD, and 23 more major/minor/exotic pairs
- **Metals** (24): XAU_USD, XAG_USD, XAU_EUR, XAU_JPY, XAU_AUD, and 19 more crosses + XCU_USD (copper), XPT_USD, XPD_USD
- **Indices** (10): SPX500_USD, NAS100_USD, US30_USD, EU50_EUR, DE30_EUR, JP225_USD, and 4 more
- **Commodities** (7): NATGAS_USD, SUGAR_USD, WHEAT_USD, SOYBN_USD, CORN_USD, WTICO_USD, BCO_USD
- **Bonds** (6): USB02Y_USD, USB05Y_USD, USB10Y_USD, USB30Y_USD, DE10YB_EUR, UK10YB_GBP — Enterprise tier only

## Tier Access

| Feature | Free | Professional | Institutional |
|---|---|---|---|
| Instruments | 4 | 15 | All 76+ |
| API calls / day | 50 | Unlimited | Unlimited |
| `verify_regime()` | ✓ | ✓ | ✓ |
| `get_entry_signal()` | — | ✓ | ✓ |
| `get_session_signal_quality()` | — | ✓ | ✓ |
| OU-calibrated entry timing | — | ✓ | ✓ |
| DML session quality (32 instruments) | — | ✓ | ✓ |
| Institutional order-flow VPIN | — | — | ✓ |
| Cross-client Network Intelligence | — | — | ✓ |

Upgrade at [gateway.deepalgo.co.uk](https://gateway.deepalgo.co.uk)

## Health Check

```python
import requests
r = requests.get("https://api.deepalgo.co.uk/health")
print(r.json())
```

## Bloomberg EMSX Integration

Running orders through Bloomberg EMSX? The SDK includes a pre-trade hook that gates every order through Sovereign's regime check before it reaches the book — producing a MiFID II Article 27 pre-trade audit artefact on every decision.

```python
from deepalgo_sovereign.emsx import SovereignEMSXHook

hook = SovereignEMSXHook(api_key="YOUR_SOVEREIGN_KEY")

# Before submitting to EMSX:
decision = hook.check_regime("EURUSD")   # Bloomberg ticker format

if decision.approved:
    # submit order to EMSX normally
    pass
else:
    print(f"Order blocked: {decision.gate} — {decision.reason}")
    record = hook.audit_record(decision, order_ref="ORD-001")
    # store record for MiFID II best-execution evidence
```

**Supported tickers:** Bloomberg FX (`EURUSD`, `GBPUSD`, `USDJPY`…), metals (`XAUUSD`, `XAGUSD`), and index futures (`NQ1 Index`, `ES1 Index`, `YM1 Index`, `DAX Index`…). Full map in `deepalgo_sovereign/emsx.py`.

**Timeout behaviour:** if Sovereign is unreachable within 10 seconds, the hook defaults to APPROVE — your order workflow is never blocked by an API outage.

**No Bloomberg credentials required** — the hook calls Sovereign's API, not Bloomberg's. Your existing EMSX session and `blpapi` setup are unchanged.

## Not using Python? MetaTrader (MQL5) EA

Trading on MetaTrader 5 instead of a Python stack? [`mql5/DeepAlgoSovereignGate.mq5`](../mql5/README.md) wraps this same API in a free, no-code Expert Advisor — drag it onto a chart, paste your API key, and it publishes the same APPROVE/VETO verdict (regime, veto reason, VPIN, confidence) on the chart and via a `GlobalVariable`/Common file that any other EA on your terminal can read.

## Trading over a FIX session?

[`sovereign_fix_proxy/`](../sovereign_fix_proxy/README.md) is a local proxy that sits between your bot and your broker's FIX endpoint, gating every `NewOrderSingle` against Sovereign in under 1ms with no changes to your bot beyond pointing it at a local port. Useful when your execution stack isn't Python and a REST/SDK integration isn't practical.

## Support

- Documentation: [gateway.deepalgo.co.uk](https://gateway.deepalgo.co.uk)
- Email: support@deepalgo.co.uk

---

*DeepAlgo Sovereign SDK v0.2.4 — MIT License*
