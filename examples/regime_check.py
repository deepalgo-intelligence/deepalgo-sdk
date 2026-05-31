"""
Basic regime check — verify whether an instrument is in a favorable
mean-reversion regime before entering a trade.
"""
from deepalgo_sovereign import DeepAlgoClient

client = DeepAlgoClient(api_key="your_key_here")

regime = client.verify_regime("EUR_USD")

if regime["is_favorable"]:
    print(f"EUR/USD: regime favorable — {regime['stability_score']} stability")
else:
    print(f"EUR/USD: regime vetoed — {regime['veto_reason']}")
    print(f"  Regime type: {regime['metrics']['regime']}")
