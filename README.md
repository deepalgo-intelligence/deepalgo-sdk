# DeepAlgo Sovereign SDK

Python client for the [DeepAlgo Sovereign](https://deepalgo.co.uk) AI Regime API — institutional-grade regime classification, entry signal quality, and order-flow intelligence across FX, metals, indices, and commodities.

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
print(regime)
# {
#   "is_favorable": True,
#   "regime_label": "MEAN_REVERTING",
#   "lock1_pass": True,
#   "lock2_pass": True,
#   "lock3_pass": True,
#   "veto_reason": None
# }
```

### 3. Check entry signal quality

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
| `is_favorable` | bool | `True` if all active locks pass |
| `regime_label` | str | `MEAN_REVERTING`, `TRENDING`, or `NEUTRAL` |
| `lock1_pass` | bool | Regime Classification gate |
| `lock2_pass` | bool | Structural Noise Filter gate |
| `lock3_pass` | bool | Sequence Validation gate (only if `use_tlock=True`) |
| `veto_reason` | str \| None | Reason for veto if `is_favorable` is `False` |

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
| OU-calibrated entry timing | — | ✓ | ✓ |
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

*DeepAlgo Sovereign SDK v0.2.0 — MIT License*
