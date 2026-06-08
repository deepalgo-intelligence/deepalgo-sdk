# DeepAlgo Sovereign SDK

Python client for the [DeepAlgo Sovereign](https://deepalgo.co.uk) AI Regime API — institutional-grade regime classification, entry signal quality, session-stratified causal signal quality, and order-flow intelligence across FX, metals, indices, and commodities.

## Installation

```bash
pip install deepalgo-sovereign
```

## Quick Start

### 1. Get a free API key

```python
from deepalgo_sovereign import DeepAlgoClient

DeepAlgoClient.enroll("you@email.com")
# Your API key arrives in your inbox within seconds — no card required.
```

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

# EUR/USD in Asian hours: 99.6% of raw OFI signal is macro noise — not structural.
# USD/JPY in Asian hours: only 2.7% spurious — Tokyo institutional flow is genuine.

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

Returns the AI regime verdict for an instrument.

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
| `metrics.regime` | str | HMM state — `"MEAN_REVERTING"`, `"TRENDING"`, `"HIGH_VOL"` |
| `metrics.composite_confidence` | float | Combined confidence after all scalars applied |
| `metrics.entropy` | float | Shannon entropy of return distribution (0–1) |
| `metrics.vpin_at_time` | float | VPIN at scan time — > 0.80 = predatory flow |
| `metrics.entropy_scalar` | float | Confidence multiplier from entropy (1.0 = no reduction) |
| `metrics.vpin_scalar` | float | Confidence multiplier from order-flow toxicity |
| `metrics.macro_z_score` | float | Z-score vs macro driver spread |
| `metrics.lock3_score` | float | Transformer sequence validation score |

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
| `forensics.failed_lock` | str | Which lock blocked, or `"NONE"` |
| `forensics.vpin_toxicity` | float | Current VPIN — > 0.75 = toxic |
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

**Research note:** The Asian session finding is the sharpest result. EUR/USD in Asian hours (00–08 UTC) loses 99.6% of its apparent OFI signal to confounder exposure — it is almost entirely spurious. USD/JPY in the same session loses only 2.7% — Tokyo institutional participation is genuine. The difference is not in the signal. It is in who is trading. Source: *DeepAlgo Sovereign Research, Bletchley Intelligence Ltd.*

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

### `client.validate_sequence(asset, candles)`

Runs the full validation stack using 60 M5 candles of OHLCV data.

```python
result = client.validate_sequence("EUR_USD", candles=[...])  # list of 60 OHLCV dicts
# {"is_authorized": True, "verdict": "AUTHORIZED"}
```

## Supported Instruments

The API covers 76+ instruments across four asset classes:

- **FX**: EUR_USD, GBP_USD, USD_JPY, EUR_JPY, GBP_JPY, AUD_USD, and 30+ major/minor/exotic pairs
- **Metals**: XAU_USD, XAG_USD, XAU_EUR, XAU_JPY, XAU_AUD
- **Indices**: SPX500_USD, NAS100_USD, US30_USD, EU50_EUR, DE30_EUR, JP225_USD
- **Commodities**: NATGAS_USD, SUGAR_USD, WHEAT_USD, SOYBN_USD, CORN_USD

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

## Support

- Documentation: [deepalgo.co.uk](https://deepalgo.co.uk)
- Email: support@deepalgo.co.uk

---

*DeepAlgo Sovereign SDK v0.2.2 — MIT License*
