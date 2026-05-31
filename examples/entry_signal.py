"""
Entry signal quality check — combines regime validation with OU-calibrated
entry timing. Only enter when both the regime is favorable AND entry quality
is HIGH or MEDIUM.
"""
from deepalgo_sovereign import DeepAlgoClient

client = DeepAlgoClient(api_key="your_key_here")

instruments = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD"]

for instrument in instruments:
    signal = client.get_entry_signal(instrument)
    regime = client.verify_regime(instrument)

    quality = signal["entry_quality"]
    favorable = regime["is_favorable"]

    if favorable and quality in ("HIGH", "MEDIUM"):
        print(f"{instrument}: ENTER — {quality} quality | "
              f"OU z={signal['current_ou_z']:.2f} | "
              f"wait {signal['recommended_delay_candles']} candles | "
              f"confirm with {signal['best_confirmation_signal']}")
    else:
        reason = regime.get("veto_reason") or f"entry quality {quality}"
        print(f"{instrument}: SKIP — {reason}")
