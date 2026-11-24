import time
import requests


class ExecutionResult:
    """Combined regime verdict + fill benchmark returned by ``execute_and_track()``.

    Regime fields (always present)::

        result.is_favorable   → bool   — True if regime gate passed
        result.verdict        → str    — 'APPROVED' or 'VETO'
        result.veto_reason    → str|None — reason code when vetoed
        result.regime         → dict   — full raw regime response

    Fill benchmark fields (None when ``slippage_pips`` / ``venue`` not provided)::

        result.your_percentile           → int|None  — % of network with worse slippage
        result.recommended_venue_next_time → str|None — best venue from collective fills
        result.potential_saving_pips     → float|None — saving vs network median
        result.network_sample_size       → int|None  — fills in benchmark bucket
        result.fill_verdict              → str|None  — ABOVE_MEDIAN | AT_MEDIAN | BELOW_MEDIAN
        result.fill_benchmark            → dict|None — full raw fill response
    """

    def __init__(self, regime: dict, fill_benchmark: dict | None = None):
        self._regime = regime
        self._fill   = fill_benchmark or {}

    # ── regime properties ──────────────────────────────────────────────────────

    @property
    def is_favorable(self) -> bool:
        return bool(self._regime.get("is_favorable", False))

    @property
    def verdict(self) -> str:
        if "verdict" in self._regime:
            return str(self._regime["verdict"])
        return "APPROVED" if self.is_favorable else "VETO"

    @property
    def veto_reason(self) -> str | None:
        return self._regime.get("veto_reason")

    @property
    def regime(self) -> dict:
        return self._regime

    # ── fill benchmark properties (None when no fill submitted) ────────────────

    @property
    def your_percentile(self) -> int | None:
        v = self._fill.get("your_percentile")
        return int(v) if v is not None else None

    @property
    def recommended_venue_next_time(self) -> str | None:
        return self._fill.get("recommended_venue_next_time")

    @property
    def potential_saving_pips(self) -> float | None:
        v = self._fill.get("potential_saving_pips")
        return float(v) if v is not None else None

    @property
    def network_sample_size(self) -> int | None:
        v = self._fill.get("network_sample_size")
        return int(v) if v is not None else None

    @property
    def fill_verdict(self) -> str | None:
        return self._fill.get("verdict")

    @property
    def fill_benchmark(self) -> dict | None:
        return self._fill if self._fill else None

    def __repr__(self) -> str:
        parts = [f"verdict={self.verdict!r}"]
        if self.your_percentile is not None:
            parts.append(f"your_percentile={self.your_percentile}")
        return f"ExecutionResult({', '.join(parts)})"


class DeepAlgoClient:
    @classmethod
    def enroll(cls, email: str, base_url: str = "https://api.deepalgo.co.uk") -> None:
        """
        Register for a free API key. Your key is emailed within seconds — no card required.

        Three-step flow::

            # Step 1 — request your key (returns immediately)
            DeepAlgoClient.enroll("you@email.com")

            # Step 2 — check your inbox (including spam) for the welcome email
            #           containing your API key (arrives within ~5 seconds)

            # Step 3 — use the key
            client = DeepAlgoClient(api_key="da_free_xxxxxxxxxxxx")
            regime = client.verify_regime("EUR_USD")

        If the email address is already registered, your existing key is resent.
        """
        url = f"{base_url.rstrip('/')}/register/free"
        try:
            r = requests.post(url, json={"email": email}, timeout=15)
            if r.status_code in (200, 201):
                print(r.json().get("message", "Check your inbox for your API key."))
            elif r.status_code == 429:
                print("Rate limit reached — please wait an hour and try again.")
            elif r.status_code == 422:
                detail = r.json().get("detail", "Please supply a valid email address.")
                print(detail)
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

    def verify_regime(self, asset: str, use_tlock: bool = True, strategy_type: str = "mean_reversion"):
        """
        Full AI regime check for a specific asset.

        This endpoint fetches live market data and runs the regime gauntlet
        matched to ``strategy_type``. Response time is typically 2–8 seconds
        depending on market data latency.

        **For production / high-frequency use**: call ``check_lock()`` instead.
        It reads from a pre-computed Redis cache updated every 60 seconds and
        responds in under 100 ms — no live data fetch.

        Use ``verify_regime()`` when:
        - You want a fresh on-demand check during strategy development
        - You are evaluating an instrument for the first time
        - You want the full regime metadata (confidence, entropy, VPIN percentile)

        Use ``check_lock()`` when:
        - You are routing orders in real-time and need a fast binary EXECUTE/VETO
        - You are polling on every bar in a live strategy loop

        :param asset: The instrument name (e.g., 'EUR_USD')
        :param use_tlock: Toggle the Transformer Lock (Lock 3). Default True.
            Only meaningful for ``strategy_type='mean_reversion'``.
        :param strategy_type: ``'mean_reversion'`` (default, the original
            four-signal gauntlet — HMM mean-reversion state, Neural Proxy,
            entropy, Transformer sequence score) or ``'trend'`` (2026-11-17,
            a different lens on the same endpoint for trend/momentum entries
            — a deliberately lighter two-signal check, since the two MR-
            trained classifiers above would give wrong answers on a trending
            market; check the response's ``evaluated_checks`` field for
            exactly what ran). ``carry``/``divergence`` are planned, not yet
            available — passing either raises a 422 from the API, not a
            silent fallback to the default.

        **Enforcement is opt-in (2026-11-22):** the response always includes
        ``would_veto`` (what the raw gauntlet concluded), ``enforcement_mode``
        (your account's setting — ``'monitor_only'`` by default), and
        ``holdback_reason``. ``is_favorable`` reflects what actually happened
        for you, which is ``True`` whenever ``enforcement_mode`` is
        ``'monitor_only'`` even if ``would_veto`` is ``True`` — call
        ``set_enforcement_mode('enforce')`` if you want a raw veto to
        actually be reflected as unfavorable (subject to a randomised
        hold-back on a fraction of enforce-mode events, by design).
        """
        # We pass the toggles as query parameters
        url = f"{self.base_url}/regime/{asset}"
        params = {"use_tlock": str(use_tlock).lower(), "strategy_type": strategy_type}

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
        bond instruments (DeepAlgo Sovereign Research, DeepAlgo Ltd).
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

    def get_decision(self, instrument: str, position_state: str,
                      exposure_side: str = None, hold_hours_so_far: float = None,
                      lookahead_hours: float = 12.0) -> dict:
        """
        Returns the unified five-action decision for an instrument, composing
        the regime/entry/session-quality gates (flat) or hedge-timing/risk-
        warehousing advisories (holding) into a single recommendation.

        :param instrument: OANDA instrument name (e.g. 'EUR_USD', 'XAU_USD')
        :param position_state: 'flat' (no position, considering entry) or
            'holding' (already holding, considering continue vs. hedge)
        :param exposure_side: required when position_state='holding' —
            'long' or 'short', the side of the EXISTING position
        :param hold_hours_so_far: required when position_state='holding' —
            active-hours this position has been open
        :param lookahead_hours: only used when position_state='holding'
        :returns: dict with keys:

            - instrument      (str)
            - position_state  (str): 'flat' | 'holding'
            - action          (str): 'act_now' | 'delay_action' | 'reject_action'
              (flat only) | 'maintain_current_state' | 'transfer_risk' (holding only)
            - reason          (str): plain-English reason for the action
            - signals         (dict): the raw underlying signal values used
            - recheck_after_minutes (float, only present when action='delay_action')
            - experimental_confidence_check (dict, flat only, advisory -- never
              changes `action`; see its own 'note' field)

        On any request failure, returns action='delay_action' — the safe
        default (retry shortly) rather than silently proceeding or blocking
        permanently.

        Usage::

            d = client.get_decision('EUR_USD', position_state='flat')
            if d['action'] == 'act_now':
                # proceed with entry
                pass
        """
        params = {"position_state": position_state}
        if exposure_side is not None:
            params["exposure_side"] = exposure_side
        if hold_hours_so_far is not None:
            params["hold_hours_so_far"] = hold_hours_so_far
        if position_state == "holding":
            params["lookahead_hours"] = lookahead_hours

        url = f"{self.base_url}/decision/{instrument}"
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "instrument": instrument,
                "position_state": position_state,
                "action": "delay_action",
                "reason": "Decision check failed — defaulting to the safe retry action.",
                "signals": {},
                "recheck_after_minutes": 5.0,
                "error": str(e),
            }

    def get_decision_breadth(self) -> dict:
        """
        Returns the current market-wide breadth of Act Now / Delay / Reject
        across the tracked instrument universe -- "how much of the market
        is currently favourable for entry." Not a network effect (the same
        for every client) -- see the endpoint's own docstring.

        :returns: dict with action_distribution, dominant_action,
            network_instruments_tracked, computed_at -- or
            {"status": "INSUFFICIENT_DATA"} if too few instruments have
            resolved yet.
        """
        url = f"{self.base_url}/benchmark/decision-breadth"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "INSUFFICIENT_DATA", "error": str(e)}

    def submit_decision_outcome(self, instrument: str, action_received: str,
                                 favorable: bool, assessed_at: str = None) -> dict:
        """
        Reports back whether a previously-received get_decision() verdict
        actually turned out favourable. Anonymised on ingest -- your
        api_key is never stored. This is the genuine network-effect half
        of the decision framework: more clients reporting real outcomes
        improves get_decision_accuracy() for everyone, not just you.

        Usage::

            d = client.get_decision('EUR_USD', position_state='flat')
            # ... later, once you know how it played out ...
            client.submit_decision_outcome('EUR_USD', d['action'], favorable=True)
        """
        url = f"{self.base_url}/decision/outcome"
        payload = {"instrument": instrument, "action_received": action_received,
                   "favorable": favorable, "assessed_at": assessed_at}
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}

    def get_decision_accuracy(self) -> dict:
        """
        Returns the pooled, anonymised, client-reported empirical accuracy
        per /decision/ action type -- how often 'act_now' verdicts (etc.)
        actually turned out well, across the whole client base.

        :returns: dict with by_action (per-action n + favorable_rate, or
            INSUFFICIENT_DATA if fewer than 10 real reports) and
            total_outcomes.
        """
        url = f"{self.base_url}/benchmark/decision-accuracy"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"by_action": {}, "total_outcomes": 0, "error": str(e)}

    def get_fill_quality(self, instrument: str) -> dict:
        """
        Returns a real-time execution quality advisory based on live market
        microstructure conditions.

        This endpoint does **not** require or observe your firm's fill data.
        The advisory is derived from VPIN toxicity, realized-volatility ratio,
        and AR1 momentum — signals Sovereign observes in the market, not in
        your execution records.

        :param instrument: OANDA instrument name (e.g. 'EUR_USD', 'NAS100_USD')
        :returns: dict with keys:

            - instrument              (str):   normalised instrument name
            - execution_tier          (str):   'OPTIMAL' | 'ACCEPTABLE' | 'DEGRADED' | 'HOSTILE'
            - recommendation          (str):   'PROCEED' | 'SIZE_DOWN' | 'DELAY' | 'AVOID'
            - adverse_fill_probability (float): estimated probability of adverse fill [0–1]
            - expected_slippage_pips  (dict):  {'low': float, 'high': float}
            - primary_driver          (str):   dominant condition driving the tier
            - conditions_note         (str):   plain-English explanation
            - recommended_venue       (str):   best venue for this instrument right now
            - venue_quality_scores    (dict):  {venue: score 0–100} from collective client fills
            - data_quality            (str):   'preliminary_synthetic' | 'production'
            - signals_observed        (dict):  raw microstructure signals used
            - basis                   (str):   'market_microstructure_signal'
            - sources                 (list):  academic citations

        **execution_tier** interpretation::

            OPTIMAL     VPIN < 0.20 — minimal adverse selection, lowest expected slippage
            ACCEPTABLE  Normal conditions — proceed at standard size
            DEGRADED    VPIN > 0.40 or high RV — size down or delay
            HOSTILE     Active VPIN spike — avoid execution until normalised

        **MiFID II Article 27 note:** The timestamped response from this endpoint
        constitutes pre-trade best-execution evidence for RTS 28 reporting — an
        independent, timestamped microstructure score at the moment of the decision.

        Usage::

            fq = client.get_fill_quality("EUR_USD")
            print(fq["execution_tier"])           # "DEGRADED"
            print(fq["recommendation"])           # "SIZE_DOWN"
            print(fq["adverse_fill_probability"]) # 0.38

            # Wire into sizing decision
            regime = client.verify_regime("EUR_USD")
            if regime["is_favorable"]:
                fq = client.get_fill_quality("EUR_USD")
                if fq["recommendation"] == "AVOID":
                    pass  # defer
                elif fq["recommendation"] == "SIZE_DOWN":
                    units = int(units * 0.6)
        """
        url = f"{self.base_url}/fill-quality/{instrument}"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "instrument":               instrument,
                "execution_tier":           "ACCEPTABLE",
                "recommendation":           "PROCEED",
                "adverse_fill_probability": 0.20,
                "expected_slippage_pips":   {"low": 0.3, "high": 0.8},
                "primary_driver":           "UNAVAILABLE",
                "conditions_note":          "Advisory unavailable — proceeding at standard conditions.",
                "recommended_venue":        "oanda",
                "venue_quality_scores":     {},
                "data_quality":             "unavailable",
                "signals_observed":         {},
                "basis":                    "fallback",
                "error":                    str(e),
            }

    def get_instrument_catalog(
        self,
        tier: str = "",
        asset_class: str = "",
        include_live_toxicity: bool = True,
    ) -> dict:
        """
        Browse the instrument catalog: every instrument Sovereign covers,
        which tier unlocks it, its asset class, a relative volatility
        bucket, typical spread, and (optionally) its current live VPIN
        toxicity tier.

        Available at every tier, including FREE — this is a reference/
        browse call, not a per-instrument signal, so a client can see
        what unlocks at the next tier up before deciding to upgrade.

        :param tier: filter to one tier's catalog — 'FREE' | 'PROFESSIONAL' | 'INSTITUTIONAL' | 'ENTERPRISE'
        :param asset_class: filter to one asset class — 'FX' | 'INDICES' | 'BONDS' | 'COMMODITIES' | 'METALS'
        :param include_live_toxicity: set False to skip the live Redis read and return static fields only (faster)
        :returns: dict with keys:

            - your_tier          (str|None): the calling key's own tier
            - count              (int):      number of instruments in `instruments`
            - catalog_built_at   (str|None): when the static vol/spread data was last built
            - instruments        (list[dict]): one row per instrument —

                - short_name              (str):  the exact code every other Sovereign
                  endpoint uses (e.g. 'EUR_USD') — intentionally not a separate
                  "generic" symbology, so this value can be passed straight into
                  verify_regime()/get_fill_quality()/get_entry_signal() unchanged
                - full_name               (str):  human-readable name, e.g. "Euro / US Dollar"
                - asset_class             (str):  'FX' | 'INDICES' | 'BONDS' | 'COMMODITIES' | 'METALS'
                - min_tier                (str):  lowest tier that unlocks this instrument
                - available_to_you        (bool): whether your own key can query it today
                - realized_vol_annualized_pct (float|None)
                - vol_bucket              (str|None): 'LOW'|'MEDIUM'|'HIGH'|'EXTREME' — a RELATIVE
                  percentile rank within the full universe, not an absolute cutoff
                - avg_spread_pips         (float|None)
                - current_toxicity_tier   (str|None): 'OPTIMAL'|'ACCEPTABLE'|'DEGRADED'|'HOSTILE'|None —
                  a lightweight live VPIN read; for an execution decision on one
                  specific instrument, call get_fill_quality() instead, which
                  layers in regime/AR1/RV on top of VPIN

            - by_tier (dict[str, list[str]]): each tier's full catalog, for reference

        Usage::

            cat = client.get_instrument_catalog(tier="INSTITUTIONAL", asset_class="FX")
            hostile_now = [i["short_name"] for i in cat["instruments"]
                           if i["current_toxicity_tier"] == "HOSTILE"]
        """
        url = f"{self.base_url}/instruments"
        params = {"include_live_toxicity": include_live_toxicity}
        if tier:
            params["tier"] = tier
        if asset_class:
            params["asset_class"] = asset_class
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "your_tier": None, "count": 0, "catalog_built_at": None,
                "instruments": [], "by_tier": {}, "error": str(e),
            }

    def submit_fill(
        self,
        instrument:       str,
        venue:            str,
        slippage_pips:    float,
        adverse_fill:     bool,
        *,
        side:             str | None   = None,
        vpin_at_fill:     float | None = None,
        session:          str | None   = None,
        regime_state:     str | None   = None,
        order_size_units: int | None   = None,
    ) -> dict:
        """
        Submit an anonymised post-trade fill observation for collective venue intelligence.

        Sovereign aggregates fill data across all participating clients to compute
        collective venue quality scores returned in ``get_fill_quality()``
        as ``recommended_venue`` and ``venue_quality_scores``.

        **Your api_key is never stored.**  All data is anonymised on ingest —
        only market conditions (instrument, venue, slippage, session) are retained.

        **Sovereign and Enterprise tiers only.**

        :param instrument:       OANDA instrument name (e.g. ``'EUR_USD'``)
        :param venue:            Broker/venue used (e.g. ``'oanda'``, ``'lmax'``, ``'ib'``)
        :param slippage_pips:    Observed slippage in pips (positive = adverse, negative = favourable)
        :param adverse_fill:     True if the fill was worse than the signal price
        :param side:             ``'BUY'`` or ``'SELL'`` (optional)
        :param vpin_at_fill:     VPIN score at time of fill (optional — enriches the model)
        :param session:          ``'ASIAN'`` / ``'LONDON'`` / ``'NY'`` / ``'OFF'`` (optional)
        :param regime_state:     Regime label at fill time (optional)
        :param order_size_units: Order size in units (optional)
        :returns: ``{'status': 'accepted', 'instrument': str}`` on success

        Usage::

            # After your trade fills:
            client.submit_fill(
                instrument="EUR_USD",
                venue="lmax",
                slippage_pips=0.4,
                adverse_fill=False,
                side="BUY",
                session="LONDON",
            )

            # The next call to get_fill_quality() will reflect collective data:
            fq = client.get_fill_quality("EUR_USD")
            print(fq["recommended_venue"])      # "lmax"
            print(fq["venue_quality_scores"])   # {"lmax": 84.5, "oanda": 71.2}
        """
        url = f"{self.base_url}/execution/fill"
        payload = {
            "instrument":       instrument,
            "venue":            venue,
            "slippage_pips":    slippage_pips,
            "adverse_fill":     adverse_fill,
            "side":             side,
            "vpin_at_fill":     vpin_at_fill,
            "session":          session,
            "regime_state":     regime_state,
            "order_size_units": order_size_units,
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}

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

            - ``authorized`` (bool): True = EXECUTE, False = BLOCK — reflects what
              actually happened for you, not just the raw gauntlet verdict
            - ``decision`` (str): ``"EXECUTE"`` or ``"BLOCK"``
            - ``would_veto`` (bool): the raw gauntlet's own verdict, regardless of
              your enforcement setting
            - ``enforcement_mode`` (str): ``'monitor_only'`` (default) or ``'enforce'``
            - ``holdback_reason`` (str | None): why a raw veto wasn't enforced, if
              applicable (``'client_monitor_only_mode'`` or ``'random_holdback'``)
            - ``forensics.failed_lock`` (str): which lock the raw gauntlet flagged, or ``"NONE"``
            - ``forensics.vpin_toxicity`` (float): current VPIN score
            - ``forensics.pip_multiplier`` (int): correct pip factor for this instrument
            - ``forensics.execution_intelligence``: VWAP deviation, slippage estimate,
              suggested max clip size

        **Enforcement is opt-in** — every account defaults to ``monitor_only``
        (``authorized`` is always ``True`` unless you've opted in, regardless of
        ``would_veto``). Call ``set_enforcement_mode('enforce')`` to have a raw
        veto actually block the trade, subject to a randomised hold-back on a
        fraction of enforce-mode events, by design.

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

    def get_enforcement_mode(self) -> dict:
        """
        Read this account's current veto enforcement mode.

        Every account defaults to ``'monitor_only'``: ``verify_regime()`` and
        ``check_lock()`` both always report the raw gauntlet verdict via
        ``would_veto``, but nothing is actually blocked unless you've opted
        into ``'enforce'`` — and even then, a random fraction of would-be
        vetoes are deliberately held back rather than acted on, so a genuine
        comparison group exists for evaluating whether enforcement helps.

        :returns: dict with keys ``mode``, ``holdback_prob_if_enforce``, ``note``

        Usage::

            mode = client.get_enforcement_mode()
            print(mode["mode"])  # "monitor_only"
        """
        url = f"{self.base_url}/enforcement-mode"
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"mode": "monitor_only", "error": str(e)}

    def set_enforcement_mode(self, mode: str) -> dict:
        """
        Set this account's veto enforcement mode.

        :param mode: ``'enforce'`` to have a raw veto actually block the order
            (subject to the random hold-back described in ``get_enforcement_mode()``),
            or ``'monitor_only'`` (the default) to only ever receive the raw
            verdict without anything being blocked.
        :returns: ``{'mode': str, 'status': 'updated'}`` on success

        Usage::

            client.set_enforcement_mode("enforce")
        """
        url = f"{self.base_url}/enforcement-mode"
        try:
            response = requests.post(url, json={"mode": mode}, headers=self.headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}

    def execute_and_track(
        self,
        instrument:       str,
        *,
        slippage_pips:    float | None = None,
        venue:            str | None   = None,
        adverse_fill:     bool         = False,
        side:             str | None   = None,
        vpin_at_fill:     float | None = None,
        session:          str | None   = None,
        regime_state:     str | None   = None,
        order_size_units: int | None   = None,
        use_tlock:        bool         = True,
    ) -> "ExecutionResult":
        """
        Verify regime AND submit a fill observation in one call.

        Returns an :class:`ExecutionResult` combining the regime verdict with an
        immediate peer benchmark comparison.  When ``slippage_pips`` and ``venue``
        are omitted the call behaves identically to ``verify_regime()`` but still
        returns an ``ExecutionResult`` — adoption is zero-friction for existing callers.

        :param instrument:       OANDA instrument name (e.g. ``'EUR_USD'``)
        :param slippage_pips:    Observed slippage in pips — supply to trigger fill
            submission and receive a peer benchmark in the response.
        :param venue:            Broker/venue used (e.g. ``'oanda'``, ``'lmax'``).
            Required alongside ``slippage_pips`` to submit a fill.
        :param adverse_fill:     True if the fill was worse than the signal price.
        :param side:             ``'BUY'`` or ``'SELL'`` (optional)
        :param vpin_at_fill:     VPIN score at fill time (optional)
        :param session:          ``'ASIAN'`` / ``'LONDON'`` / ``'NY'`` (optional)
        :param regime_state:     Regime label at fill time (optional)
        :param order_size_units: Order size in units (optional)
        :param use_tlock:        Toggle Transformer Lock 3. Default True.
        :returns: :class:`ExecutionResult`

        Usage — replace two manual calls with one::

            # Before (two steps — easy to forget the second):
            verdict = client.verify_regime("EUR_USD")
            client.submit_fill("EUR_USD", slippage_pips=1.2, venue="oanda",
                               adverse_fill=False)

            # After (one call — fill submission is automatic):
            result = client.execute_and_track(
                instrument    = "EUR_USD",
                slippage_pips = 1.2,
                venue         = "oanda",
                adverse_fill  = False,
            )
            result.verdict                    # "APPROVED"
            result.your_percentile            # 38
            result.recommended_venue_next_time # "lmax"
            result.potential_saving_pips       # 0.3

            # Without fill args — identical to verify_regime():
            result = client.execute_and_track("EUR_USD")
            result.is_favorable               # True / False
            result.your_percentile            # None
        """
        regime = self.verify_regime(instrument, use_tlock=use_tlock)

        fill_benchmark: dict | None = None
        if slippage_pips is not None and venue is not None:
            raw = self.submit_fill(
                instrument       = instrument,
                venue            = venue,
                slippage_pips    = slippage_pips,
                adverse_fill     = adverse_fill,
                side             = side,
                vpin_at_fill     = vpin_at_fill,
                session          = session,
                regime_state     = regime_state,
                order_size_units = order_size_units,
            )
            # Strip envelope fields; keep only the benchmark payload
            fill_benchmark = {
                k: v for k, v in raw.items()
                if k not in ("status", "instrument")
            }

        return ExecutionResult(regime=regime, fill_benchmark=fill_benchmark)