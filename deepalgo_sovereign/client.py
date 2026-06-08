import time
import requests

class DeepAlgoClient:
    @classmethod
    def enroll(cls, email: str, base_url: str = "https://api.deepalgo.co.uk") -> None:
        """
        Register for a free API key. Your key is emailed within seconds — no card required.

        Usage::
            DeepAlgoClient.enroll("you@email.com")
            # Check your inbox, then:
            client = DeepAlgoClient(api_key="your_key_here")
        """
        url = f"{base_url.rstrip('/')}/register/free"
        try:
            r = requests.post(url, json={"email": email}, timeout=15)
            if r.status_code in (200, 201):
                print(r.json().get("message", "Check your inbox for your API key."))
            elif r.status_code == 429:
                print("Rate limit reached — please wait an hour and try again.")
            elif r.status_code == 422:
                print("Please supply a valid email address.")
            else:
                print(f"Registration failed ({r.status_code}). Contact support@deepalgo.co.uk")
        except Exception as exc:
            print(f"Connection error: {exc}\nVisit https://gateway.deepalgo.co.uk to register.")

    def __init__(self, api_key: str, base_url: str = "https://api.deepalgo.co.uk"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "X-DeepAlgo-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self._regime_cache: dict = {}   # {asset: {"data": ..., "ts": float}}
        self._cache_ttl: int    = 300   # seconds before cache entry expires

    def verify_regime(self, asset: str, use_tlock: bool = True):
        """
        Checks the AI Regime (Lock 1, 2 & 3) for a specific asset.
        :param asset: The instrument name (e.g., 'EUR_USD')
        :param use_tlock: Boolean toggle to enable/disable the Transformer Lock (Lock 3)
        """
        # We pass the toggle as a query parameter
        url = f"{self.base_url}/regime/{asset}"
        params = {"use_tlock": str(use_tlock).lower()}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()
            self._regime_cache[asset] = {"data": data, "ts": time.time()}
            return data
        except requests.exceptions.RequestException as e:
            cached = self._regime_cache.get(asset)
            if cached and (time.time() - cached["ts"]) < self._cache_ttl:
                cached_data = dict(cached["data"])
                cached_data["_cached"] = True
                return cached_data
            return {"is_favorable": False, "veto_reason": f"CONNECTION_ERROR: {str(e)}"}

    def get_entry_signal(self, instrument: str) -> dict:
        """
        Returns the OU-calibrated entry signal quality for an instrument.

        :param instrument: OANDA instrument name (e.g. 'EUR_USD', 'XAU_USD')
        :returns: dict with keys:
            - entry_quality  (str):  'HIGH' | 'MEDIUM' | 'LOW' | 'NO_DATA'
            - current_ou_z   (float): live OU z-score — distance from OU equilibrium in σ
            - ou_z_threshold (float): calibrated threshold from 60-day IC analysis
            - recommended_delay_candles (int): optimal M5 candle wait after BB touch
            - best_confirmation_signal  (str): highest-IC signal at lag 5
            - calibrated (bool): False if instrument has no calibration data yet

        Usage::
            signal = client.get_entry_signal('EUR_USD')
            if signal['entry_quality'] in ('HIGH', 'MEDIUM'):
                # statistically sound entry point — proceed
                regime = client.verify_regime('EUR_USD')
        """
        url = f"{self.base_url}/entry-signal/{instrument}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"entry_quality": "NO_DATA", "current_ou_z": 0.0,
                    "calibrated": False, "error": str(e)}

    def get_session_signal_quality(self, instrument: str) -> dict:
        """
        Returns the DML-calibrated session signal quality for an instrument.

        Based on a Double Machine Learning study across 32 G10 FX, metals, and
        bond instruments (DeepAlgo Sovereign Research, Bletchley Intelligence Ltd).
        For each session, reports whether the OFI signal is structural or spurious,
        and the threshold multiplier applied internally to the Lock 3 gate.

        :param instrument: OANDA instrument name (e.g. 'EUR_USD', 'USD_JPY')
        :returns: dict with keys:

            - instrument       (str):   normalised instrument name
            - current_session  (str):   'Asian' | 'London' | 'NewYork'
            - current_quality  (str):   'STRUCTURAL' | 'MIXED' | 'SPURIOUS' | 'UNKNOWN'
            - current_multiplier (float): Lock 3 threshold multiplier active right now
            - sessions (dict):  per-session breakdown — quality, multiplier, ic_reduction_pct
            - last_calibrated  (str):   date of the most recent DML calibration run

        Multiplier interpretation::

            STRUCTURAL  1.0×  OFI signal is genuine — standard Lock 3 threshold
            MIXED       1.1×  Partial spurious component — threshold raised 10%
            SPURIOUS    1.3×  Predominantly macro noise — threshold raised 30%

        The key finding: EUR/USD in Asian hours (00–08 UTC) is 99.6% spurious.
        USD/JPY in Asian hours is only 2.7% spurious — Tokyo institutional flow
        is genuine. Session matters more than the signal itself.

        Usage::

            sq = client.get_session_signal_quality("EUR_USD")
            print(sq["current_session"])    # "Asian"
            print(sq["current_quality"])    # "SPURIOUS"
            print(sq["current_multiplier"]) # 1.3

            # Combine with regime check for highest-confidence entries
            if sq["current_quality"] != "SPURIOUS":
                regime = client.verify_regime("EUR_USD")
        """
        url = f"{self.base_url}/session-signal-quality/{instrument}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "instrument":         instrument,
                "current_session":    "UNKNOWN",
                "current_quality":    "UNKNOWN",
                "current_multiplier": 1.1,
                "sessions":           {},
                "error":              str(e),
            }

    def check_lock(self, instrument: str, injected_data: list = None) -> dict:
        """
        Binary EXECUTE / VETO decision for wiring into an execution management system.

        Reads pre-computed regime state from Redis — sub-millisecond response, no OANDA
        call on the server side.  Use this in your order-routing logic immediately before
        placing a trade.

        :param instrument: OANDA instrument name, e.g. ``'EUR_USD'``
        :param injected_data: Optional list of OHLCV dicts — substitute your own
            (e.g. LMAX) candle data instead of the server's OANDA feed.
        :returns: dict with keys:

            - ``authorized`` (bool): True = EXECUTE, False = BLOCK
            - ``decision`` (str): ``"EXECUTE"`` or ``"BLOCK"``
            - ``forensics.failed_lock`` (str): which lock blocked the trade, or ``"NONE"``
            - ``forensics.vpin_toxicity`` (float): current VPIN score
            - ``forensics.pip_multiplier`` (int): correct pip factor for this instrument
            - ``forensics.execution_intelligence``: VWAP deviation, slippage estimate,
              suggested max clip size

        Usage::

            decision = client.check_lock("EUR_USD")
            if decision["authorized"]:
                place_order()
        """
        url = f"{self.base_url}/v1/bridge/check-lock"
        payload: dict = {"instrument": instrument}
        if injected_data is not None:
            payload["injected_data"] = injected_data
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"authorized": False, "decision": "BLOCK",
                    "forensics": {"reason_code": f"CONNECTION_ERROR: {e}"}}