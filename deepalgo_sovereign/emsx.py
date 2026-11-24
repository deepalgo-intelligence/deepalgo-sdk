"""deepalgo_sovereign/emsx.py

Pre-trade Sovereign regime gate for Bloomberg EMSX.

Before any EMSX order is submitted, call check_regime(). If the Sovereign
API returns VETO, the order is blocked and the reason is logged with a
timestamp — producing a MiFID II Article 27 pre-trade audit artefact.

Usage (in your EMSX order workflow):
    from deepalgo_sovereign.emsx import SovereignEMSXHook

    hook = SovereignEMSXHook(api_key="YOUR_API_KEY")
    decision = hook.check_regime("EURUSD")   # Bloomberg ticker format
    if decision.approved:
        # submit order to EMSX
    else:
        print(f"Order blocked: {decision.gate} — {decision.reason}")

Requirements:
    pip install blpapi requests
    SOVEREIGN_API_KEY env var (or pass api_key directly)
    SOVEREIGN_API_URL env var (default: https://api.deepalgo.co.uk)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("sovereign.emsx")

# Bloomberg → OANDA instrument mapping (extend as needed)
_TICKER_MAP: dict[str, str] = {
    # FX
    "EURUSD": "EUR_USD", "GBPUSD": "GBP_USD", "USDJPY": "USD_JPY",
    "GBPJPY": "GBP_JPY", "EURJPY": "EUR_JPY", "AUDUSD": "AUD_USD",
    "USDCHF": "USD_CHF", "USDCAD": "USD_CAD", "NZDUSD": "NZD_USD",
    "EURGBP": "EUR_GBP", "EURCHF": "EUR_CHF", "AUDNZD": "AUD_NZD",
    # Metals
    "XAUUSD": "XAU_USD", "XAGUSD": "XAG_USD",
    # Indices
    "NQ1 Index":  "NAS100_USD", "ES1 Index":  "SPX500_USD",
    "YM1 Index":  "US30_USD",   "Z 1 Index":  "UK100_GBP",
    "DAX Index":  "DE30_EUR",   "SX5E Index": "EU50_EUR",
    # Energy
    "CO1 Comdty": "BCO_USD", "CL1 Comdty": "WTICO_USD",
}


@dataclass
class RegimeDecision:
    instrument:    str
    approved:      bool
    gate:          str          # e.g. "REGIME_VETO", "MICROSTRUCTURE_VETO", "APPROVED"
    reason:        str
    confidence:    float = 0.0
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_response:  Optional[dict] = field(default=None, repr=False)


class SovereignEMSXHook:
    """Pre-trade regime gate for Bloomberg EMSX order workflows."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        self.api_key  = api_key or os.getenv("SOVEREIGN_API_KEY", "")
        self.base_url = (base_url or os.getenv("SOVEREIGN_API_URL",
                         "https://api.deepalgo.co.uk")).rstrip("/")
        self.timeout  = timeout

        if not self.api_key:
            raise ValueError(
                "SOVEREIGN_API_KEY not set. "
                "Pass api_key= or set the SOVEREIGN_API_KEY env var."
            )

    def _resolve_instrument(self, bloomberg_ticker: str) -> str:
        """Convert Bloomberg ticker to OANDA instrument format."""
        upper = bloomberg_ticker.upper().replace(" ", "")
        # Direct map lookup
        for k, v in _TICKER_MAP.items():
            if k.upper().replace(" ", "") == upper:
                return v
        # FX pairs: EURUSD → EUR_USD
        clean = upper.replace("BGN", "").replace("CRNCY", "").strip()
        if len(clean) == 6 and clean.isalpha():
            return f"{clean[:3]}_{clean[3:]}"
        return bloomberg_ticker  # pass through, let API handle it

    def check_regime(self, bloomberg_ticker: str) -> RegimeDecision:
        """
        Query Sovereign for the current regime verdict.
        Returns RegimeDecision — approved=True means safe to submit to EMSX.
        """
        instrument = self._resolve_instrument(bloomberg_ticker)
        url = f"{self.base_url}/regime/{instrument}"

        try:
            resp = requests.get(
                url,
                headers={"X-API-Key": self.api_key},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            log.warning("[EMSX HOOK] Sovereign timeout for %s — defaulting APPROVE", instrument)
            return RegimeDecision(
                instrument=instrument,
                approved=True,
                gate="TIMEOUT_PASSTHROUGH",
                reason="Sovereign API timeout — order passed through",
            )
        except Exception as exc:
            log.error("[EMSX HOOK] Sovereign error for %s: %s — defaulting APPROVE", instrument, exc)
            return RegimeDecision(
                instrument=instrument,
                approved=True,
                gate="ERROR_PASSTHROUGH",
                reason=f"Sovereign API error: {exc}",
            )

        verdict    = data.get("verdict", "VETO")
        gate       = data.get("gate_triggered", "UNKNOWN")
        reason     = data.get("reason", "")
        confidence = float(data.get("confidence", 0.0))
        approved   = verdict == "APPROVED"

        decision = RegimeDecision(
            instrument=instrument,
            approved=approved,
            gate=gate if not approved else "APPROVED",
            reason=reason,
            confidence=confidence,
            raw_response=data,
        )

        if approved:
            log.info(
                "[EMSX HOOK] APPROVED  %s  confidence=%.2f  ts=%s",
                instrument, confidence, decision.timestamp_utc,
            )
        else:
            log.warning(
                "[EMSX HOOK] VETO  %s  gate=%s  reason=%s  ts=%s",
                instrument, gate, reason, decision.timestamp_utc,
            )

        return decision

    def audit_record(self, decision: RegimeDecision, order_ref: str = "") -> dict:
        """
        Return a MiFID II Article 27 pre-trade audit record.
        Log or store this alongside the order for best-execution evidence.
        """
        return {
            "order_ref":      order_ref,
            "instrument":     decision.instrument,
            "verdict":        "APPROVED" if decision.approved else "VETO",
            "gate":           decision.gate,
            "reason":         decision.reason,
            "confidence":     decision.confidence,
            "timestamp_utc":  decision.timestamp_utc,
            "data_source":    "DeepAlgo Sovereign — api.deepalgo.co.uk",
        }
