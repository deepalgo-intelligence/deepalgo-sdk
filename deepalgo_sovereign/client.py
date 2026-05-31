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
            # Pass the params into the requests.get call
            response = requests.get(url, headers=self.headers, params=params, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
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

    def validate_sequence(self, asset: str, candles: list):
        """
        Checks the full Triple-Lock (Lock 1, 2, and 3) using 60 candles.
        """
        url = f"{self.base_url}/v1/validate_sequence"
        payload = {"asset": asset, "candles": candles}
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"is_authorized": False, "verdict": "CONNECTION_ERROR", "error": str(e)}