from __future__ import annotations

"""
schwab_api.py – Thin wrapper around Schwab OAuth and option-chain endpoints.

Now supports **three** strategies:

* Covered-Call   → ``fetch_options_data()``
* Collar         → ``fetch_collar_data()``
* Call Spread    → ``fetch_call_spread_data()``

All credential handling remains internal; callers only get filtered JSON-ready
records or a ``SchwabAPIError`` on failure.
"""

import base64
import datetime as _dt
from typing import Any, Dict, List, Tuple

import requests

__all__ = ["SchwabAPI", "SchwabAPIError"]


class SchwabAPIError(RuntimeError):
    """Custom exception raised for any Schwab API–related error."""


class SchwabAPI:
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
    QUOTES_URL = "https://api.schwabapi.com/marketdata/v1/quotes"
    CHAINS_URL = "https://api.schwabapi.com/marketdata/v1/chains"

    # ------------------------------------------------------------------#
    # Construction & token management (unchanged)                       #
    # ------------------------------------------------------------------#

    def __init__(self, *, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token

        self._access_token: str | None = None
        self._token_expiry: _dt.datetime | None = None

    def _valid_access_token(self) -> str:
        if (
            self._access_token
            and self._token_expiry
            and _dt.datetime.utcnow() < self._token_expiry - _dt.timedelta(seconds=60)
        ):
            return self._access_token
        return self._refresh_access_token()

    def _refresh_access_token(self) -> str:
        creds = f"{self._client_id}:{self._client_secret}"
        auth_header = base64.b64encode(creds.encode()).decode()

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        resp = requests.post(
            self.TOKEN_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_header}",
            },
            data=data,
            timeout=30,
        )
        if resp.status_code != 200:
            raise SchwabAPIError(
                f"Token refresh failed: {resp.status_code} {resp.text}"
            )

        payload = resp.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 1800))
        self._token_expiry = _dt.datetime.utcnow() + _dt.timedelta(seconds=expires_in)
        # Handle refresh-token rotation
        if "refresh_token" in payload:
            self._refresh_token = payload["refresh_token"]
        return self._access_token

    # ------------------------------------------------------------------#
    # Covered-call (existing)                                            #
    # ------------------------------------------------------------------#

    def fetch_options_data(
        self,
        *,
        symbols: List[str],
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Covered-call helper (unchanged)."""
        records: List[Dict[str, Any]] = []
        api_calls = 0
        for sym in symbols:
            recs, calls = self._fetch_options_chain(
                symbol=sym,
                min_strike_pct=min_strike_pct,
                max_strike_pct=max_strike_pct,
                min_dte=min_dte,
                max_dte=max_dte,
            )
            records.extend(recs)
            api_calls += calls
        return records, api_calls

    # ------------------------------------------------------------------#
    # NEW – Collar strategy                                             #
    # ------------------------------------------------------------------#

    def fetch_collar_data(
        self,
        *,
        symbols: List[str],
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Return profitable **collar** opportunities for the requested symbols.

        A record is included only if the calculated `collar` (profit)
        is **positive**.
        """
        records: List[Dict[str, Any]] = []
        api_calls = 0

        for sym in symbols:
            try:
                recs, calls = self._fetch_stock_collar(
                    symbol=sym,
                    min_strike_pct=min_strike_pct,
                    max_strike_pct=max_strike_pct,
                    min_dte=min_dte,
                    max_dte=max_dte,
                )
                records.extend(recs)
                api_calls += calls
            except SchwabAPIError:
                raise
            except Exception as exc:  # pragma: no cover
                raise SchwabAPIError(f"Error processing {sym}: {exc}") from exc

        return records, api_calls

    # ------------------------------------------------------------------#
    # NEW – Call Spread strategy                                        #
    # ------------------------------------------------------------------#

    def fetch_call_spread_data(
        self,
        *,
        symbols: List[str],
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
        max_spread: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Return profitable call spread opportunities for the requested symbols.
        
        For each symbol, finds vertical call debit spreads where both options
        are ITM (in the money) and the spread is profitable.
        """
        records: List[Dict[str, Any]] = []
        api_calls = 0

        for sym in symbols:
            try:
                recs, calls = self._fetch_stock_call_spread(
                    symbol=sym,
                    min_strike_pct=min_strike_pct,
                    max_strike_pct=max_strike_pct,
                    min_dte=min_dte,
                    max_dte=max_dte,
                    max_spread=max_spread,
                )
                records.extend(recs)
                api_calls += calls
            except SchwabAPIError:
                raise
            except Exception as exc:  # pragma: no cover
                raise SchwabAPIError(f"Error processing {sym}: {exc}") from exc

        return records, api_calls

    def _fetch_stock_call_spread(
        self,
        *,
        symbol: str,
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
        max_spread: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return profitable call spread records for a single underlying."""
        records: List[Dict[str, Any]] = []
        api_calls = 0

        # ------------------ 1) Quote -----------------------------------#
        quote_resp = requests.post(
            self.QUOTES_URL,
            headers=self._auth_headers(json_req=True),
            json={"symbols": [symbol]},
            timeout=30,
        )
        api_calls += 1
        if quote_resp.status_code != 200:
            raise SchwabAPIError(
                f"Quote fetch failed for {symbol}: {quote_resp.status_code}"
            )

        quote_json = quote_resp.json()
        if symbol not in quote_json or "quote" not in quote_json[symbol]:
            raise SchwabAPIError(f"No quote data returned for {symbol}")

        price = quote_json[symbol]["quote"].get("lastPrice") or quote_json[symbol][
            "quote"
        ].get("mark")
        if not price or price <= 0:
            raise SchwabAPIError(f"Invalid price for {symbol}")

        # Strike boundaries - percentages of current price for ITM strikes
        # Both strikes should be below current price (ITM)
        min_strike = price * (min_strike_pct / 100)  # Keep as float
        max_strike = price * (max_strike_pct / 100)  # Keep as float

        # ------------------ 2) Chains ----------------------------------#
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        params = {
            "symbol": symbol,
            "contractType": "CALL",
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }
        chain_resp = requests.get(
            self.CHAINS_URL,
            params=params,
            headers=self._auth_headers(json_req=False),
            timeout=30,
        )
        api_calls += 1
        if chain_resp.status_code != 200:
            raise SchwabAPIError(
                f"Chain fetch failed for {symbol}: {chain_resp.status_code}"
            )

        chain_json = chain_resp.json()
        call_map = chain_json.get("callExpDateMap", {})

        # Iterate over expirations
        for exp_key, strike_map in call_map.items():
            # Get all strikes for this expiration and sort them
            strikes = [float(s) for s in strike_map.keys()]
            strikes.sort(reverse=True)  # Sort descending for easier iteration
            
            # Filter strikes within our range
            valid_strikes = [s for s in strikes if min_strike <= s <= max_strike]
            
            if len(valid_strikes) < 2:
                continue  # Need at least 2 strikes for a spread
                
            # For each upper strike (higher strike - the one we sell)
            for i, upper_strike in enumerate(valid_strikes):
                # Try different string formats for strike lookup
                upper_strike_str = None
                for fmt_strike in [str(upper_strike), str(int(upper_strike)), f"{upper_strike:.1f}"]:
                    if fmt_strike in strike_map:
                        upper_strike_str = fmt_strike
                        break
                
                if not upper_strike_str or upper_strike_str not in strike_map:
                    continue
                    
                upper_opts = strike_map[upper_strike_str]
                if not upper_opts:
                    continue
                    
                upper_opt = upper_opts[0]
                dte = self._calculate_dte(upper_opt["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue
                    
                upper_bid = upper_opt.get("bid", 0)
                upper_ask = upper_opt.get("ask", 0)
                if upper_bid <= 0 or upper_ask <= 0 or upper_ask < upper_bid:
                    continue
                    
                upper_mid = (upper_bid + upper_ask) / 2
                
                # For each lower strike within max_spread distance
                for lower_strike in valid_strikes[i+1:]:  # Only consider lower strikes
                    spread_width = upper_strike - lower_strike
                    if spread_width > max_spread:
                        continue  # Spread too wide
                        
                    # Try different string formats for lower strike lookup
                    lower_strike_str = None
                    for fmt_strike in [str(lower_strike), str(int(lower_strike)), f"{lower_strike:.1f}"]:
                        if fmt_strike in strike_map:
                            lower_strike_str = fmt_strike
                            break
                    
                    if not lower_strike_str or lower_strike_str not in strike_map:
                        continue
                        
                    lower_opts = strike_map[lower_strike_str]
                    if not lower_opts:
                        continue
                        
                    lower_opt = lower_opts[0]
                    lower_bid = lower_opt.get("bid", 0)
                    lower_ask = lower_opt.get("ask", 0)
                    if lower_bid <= 0 or lower_ask <= 0 or lower_ask < lower_bid:
                        continue
                        
                    lower_mid = (lower_bid + lower_ask) / 2
                    
                    # Validate that lower strike mid > upper strike mid
                    if lower_mid <= upper_mid:
                        continue
                        
                    # Calculate spread metrics
                    paid = (lower_mid - upper_mid) * 100  # Net debit paid
                    max_gain = (spread_width * 100) - paid  # Max profit
                    
                    if max_gain <= 0:
                        continue  # Only profitable spreads
                        
                    pct_gain = (max_gain / paid) * 100 if paid > 0 else 0
                    ann_pct_gain = (pct_gain * 365) / dte if dte > 0 else 0
                    
                    # Calculate strike percentage (upper strike as percentage of current price)
                    strike_pct = (upper_strike / price) * 100
                    
                    exp_ts = int(
                        _dt.datetime.fromisoformat(upper_opt["expirationDate"]).timestamp()
                    )
                    records.append(
                        {
                            "symbol": symbol,
                            "price": price,
                            "exp": exp_ts,
                            "expDate": _dt.datetime.fromtimestamp(exp_ts).strftime(
                                "%d/%m/%Y"
                            ),
                            "dte": dte,
                            "strikePct": strike_pct,
                            "lowerStrike": lower_strike,
                            "upperStrike": upper_strike,
                            "spreadWidth": spread_width,
                            "lowerBid": lower_bid,
                            "lowerAsk": lower_ask,
                            "lowerMid": lower_mid,
                            "upperBid": upper_bid,
                            "upperAsk": upper_ask,
                            "upperMid": upper_mid,
                            "paid": paid,
                            "maxGain": max_gain,
                            "pctGain": pct_gain,
                            "annPctGain": ann_pct_gain,
                        }
                    )

        return records, api_calls

    # ------------------------------------------------------------------#
    # Internal helpers – per-symbol collar logic                        #
    # ------------------------------------------------------------------#

    def _fetch_stock_collar(
        self,
        *,
        symbol: str,
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return profitable collar records for a single underlying."""
        records: List[Dict[str, Any]] = []
        api_calls = 0

        # ------------------ 1) Quote -----------------------------------#
        quote_resp = requests.post(
            self.QUOTES_URL,
            headers=self._auth_headers(json_req=True),
            json={"symbols": [symbol]},
            timeout=30,
        )
        api_calls += 1
        if quote_resp.status_code != 200:
            raise SchwabAPIError(
                f"Quote fetch failed for {symbol}: {quote_resp.status_code}"
            )

        quote_json = quote_resp.json()
        if symbol not in quote_json or "quote" not in quote_json[symbol]:
            raise SchwabAPIError(f"No quote data returned for {symbol}")

        price = quote_json[symbol]["quote"].get("lastPrice") or quote_json[symbol][
            "quote"
        ].get("mark")
        if not price or price <= 0:
            raise SchwabAPIError(f"Invalid price for {symbol}")

        # Strike boundaries
        min_strike = int(price * (min_strike_pct / 100))
        max_strike = int(price * (max_strike_pct / 100))

        # ------------------ 2) Chains ----------------------------------#
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        params = {
            "symbol": symbol,
            "contractType": "ALL",  # need calls & puts
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }
        chain_resp = requests.get(
            self.CHAINS_URL,
            params=params,
            headers=self._auth_headers(json_req=False),
            timeout=30,
        )
        api_calls += 1
        if chain_resp.status_code != 200:
            raise SchwabAPIError(
                f"Chain fetch failed for {symbol}: {chain_resp.status_code}"
            )

        chain_json = chain_resp.json()
        call_map = chain_json.get("callExpDateMap", {})
        put_map = chain_json.get("putExpDateMap", {})

        # Iterate over expirations present in **both** maps
        for exp_key, call_strikes in call_map.items():
            put_strikes = put_map.get(exp_key)
            if not put_strikes:
                continue

            for strike_str, call_opts in call_strikes.items():
                if strike_str not in put_strikes:
                    continue  # no matching put

                strike = float(strike_str)
                if strike < min_strike or strike > max_strike:
                    continue

                put_opts = put_strikes[strike_str]
                if not call_opts or not put_opts:
                    continue

                call_opt = call_opts[0]
                put_opt = put_opts[0]

                dte = self._calculate_dte(call_opt["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue

                # Validate quotes
                c_bid, c_ask = call_opt.get("bid", 0), call_opt.get("ask", 0)
                p_bid, p_ask = put_opt.get("bid", 0), put_opt.get("ask", 0)
                if min(c_bid, c_ask, p_bid, p_ask) <= 0 or c_ask < c_bid or p_ask < p_bid:
                    continue

                c_mid = (c_bid + c_ask) / 2
                p_mid = (p_bid + p_ask) / 2

                metrics = self._calculate_collar_metrics(
                    price=price,
                    strike=strike,
                    call_mid=c_mid,
                    put_mid=p_mid,
                    dte=dte,
                )
                if metrics["collar"] <= 0:
                    continue  # only profitable collars

                exp_ts = int(
                    _dt.datetime.fromisoformat(call_opt["expirationDate"]).timestamp()
                )
                records.append(
                    {
                        "symbol": symbol,
                        "price": price,
                        "exp": exp_ts,
                        "expDate": _dt.datetime.fromtimestamp(exp_ts).strftime(
                            "%d/%m/%Y"
                        ),
                        "dte": dte,
                        "strike": strike,
                        "strikePricePct": metrics["strikePricePct"],
                        "callBid": c_bid,
                        "callAsk": c_ask,
                        "callMid": c_mid,
                        "putBid": p_bid,
                        "putAsk": p_ask,
                        "putMid": p_mid,
                        **metrics,
                    }
                )

        return records, api_calls

    # ------------------------------------------------------------------#
    # Metric helpers                                                    #
    # ------------------------------------------------------------------#

    @staticmethod
    def _calculate_dte(expiration_iso: str) -> int:
        exp_date = _dt.datetime.fromisoformat(expiration_iso).date()
        return (exp_date - _dt.date.today()).days

    @staticmethod
    def _calculate_metrics(
        price: float, strike: float, bid: float, ask: float, dte: int, pct: int = 50
    ) -> Dict[str, float]:
        """(Covered-call – unchanged)"""
        call_price = bid + (pct / 100) * (ask - bid)
        cost = (price - call_price) * 100
        max_profit = (strike * 100) - cost
        pct_call = (max_profit / cost) * 100 if cost != 0 else 0
        ann_pct_call = (pct_call * 365) / dte if dte else 0
        return {
            "cost": cost,
            "maxProfit": max_profit,
            "pctCall": pct_call,
            "annPctCall": ann_pct_call,
        }

    # NEW ------------------------------------------------------------------#
    @staticmethod
    def _calculate_collar_metrics(
        *, price: float, strike: float, call_mid: float, put_mid: float, dte: int
    ) -> Dict[str, float]:
        """
        Collar metrics (all monetary values **per 100 shares**):

        * netCost  – cash outlay to enter position
        * collar   – max profit at expiration
        * annReturn – annualised % return
        * strikePricePct – strike/price ratio (%)
        """
        net_cost = (price - call_mid + put_mid) * 100
        collar = (strike - price + call_mid - put_mid) * 100
        ann_return = (
            (collar / net_cost) * (365 / dte) * 100 if net_cost and dte else 0
        )
        strike_pct = (strike / price) * 100 if price else 0

        return {
            "netCost": net_cost,
            "collar": collar,
            "annReturn": ann_return,
            "strikePricePct": strike_pct,
        }

    # ------------------------------------------------------------------#
    # Shared helper                                                     #
    # ------------------------------------------------------------------#

    def _auth_headers(self, *, json_req: bool) -> Dict[str, str]:
        hdrs = {
            "Authorization": f"Bearer {self._valid_access_token()}",
            "Accept": "application/json",
        }
        if json_req:
            hdrs["Content-Type"] = "application/json"
        return hdrs


    def _fetch_options_chain(
        self,
        *,
        symbol: str,
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        records: List[Dict[str, Any]] = []
        api_calls = 0

        # Step 1: Fetch quote
        quote_resp = requests.post(
            self.QUOTES_URL,
            headers=self._auth_headers(json_req=True),
            json={"symbols": [symbol]},
            timeout=30,
        )
        api_calls += 1
        if quote_resp.status_code != 200:
            raise SchwabAPIError(f"Quote fetch failed: {quote_resp.status_code}")
        quote_data = quote_resp.json()
        price = quote_data[symbol]["quote"].get("lastPrice") or quote_data[symbol]["quote"].get("mark")
        if not price:
            raise SchwabAPIError(f"No valid price for {symbol}")

        # Step 2: Define strike boundaries
        min_strike = int(price * (min_strike_pct / 100))
        max_strike = int(price * (max_strike_pct / 100))

        # Step 3: Fetch chain
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        params = {
            "symbol": symbol,
            "contractType": "CALL",
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }

        chain_resp = requests.get(
            self.CHAINS_URL,
            params=params,
            headers=self._auth_headers(json_req=False),
            timeout=30,
        )
        api_calls += 1
        if chain_resp.status_code != 200:
            raise SchwabAPIError(f"Chain fetch failed: {chain_resp.status_code}")
        chain_data = chain_resp.json()

        call_map = chain_data.get("callExpDateMap", {})
        for exp_date, strike_map in call_map.items():
            for strike_str, options in strike_map.items():
                strike = float(strike_str)
                if strike < min_strike or strike > max_strike:
                    continue
                option = options[0]
                dte = self._calculate_dte(option["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue
                bid = option.get("bid", 0)
                ask = option.get("ask", 0)
                if bid <= 0 or ask <= 0:
                    continue
                mid = (bid + ask) / 2
                metrics = self._calculate_metrics(price, strike, bid, ask, dte)
                if metrics["pctCall"] < 0 or metrics["annPctCall"] < 0:
                    continue
                exp_ts = int(_dt.datetime.fromisoformat(option["expirationDate"]).timestamp())
                records.append({
                    "symbol": symbol,
                    "price": price,
                    "exp": exp_ts,
                    "expDate": _dt.datetime.fromtimestamp(exp_ts).strftime("%d/%m/%Y"),
                    "dte": dte,
                    "strike": strike,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "priceStrikePct": 100 * (strike - price) / price,
                    "metrics": metrics,
                })
        return records, api_calls
