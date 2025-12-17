from __future__ import annotations

"""
schwab_api.py – Thin wrapper around Schwab OAuth and option-chain endpoints.

Now supports **six** strategies:

* Covered-Call      → ``fetch_options_data()``
* Collar            → ``fetch_collar_data()``
* Call Spread       → ``fetch_call_spread_data()``
* Put Spread        → ``fetch_put_spread_data()``
* Put-Call-Spread   → ``fetch_put_call_spread_data()``
* Iron Condor       → ``fetch_iron_condor_data()``

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
    # NEW – Put Spread strategy                                         #
    # ------------------------------------------------------------------#

    def fetch_put_spread_data(
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
        Return profitable put spread opportunities for the requested symbols.
        
        For each symbol, finds vertical put credit spreads where both options
        are OTM (out of the money) and the spread is profitable.
        """
        records: List[Dict[str, Any]] = []
        api_calls = 0

        for sym in symbols:
            try:
                recs, calls = self._fetch_stock_put_spread(
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

    def _fetch_stock_put_spread(
        self,
        *,
        symbol: str,
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
        max_spread: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return profitable put spread records for a single underlying."""
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

        # Strike boundaries - percentages of current price for OTM strikes
        # Both strikes should be below current price (OTM)
        min_strike = price * (min_strike_pct / 100)  # Keep as float
        max_strike = price * (max_strike_pct / 100)  # Keep as float

        # ------------------ 2) Chains ----------------------------------#
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        params = {
            "symbol": symbol,
            "contractType": "PUT",
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
        put_map = chain_json.get("putExpDateMap", {})

        # Iterate over expirations
        for exp_key, strike_map in put_map.items():
            # Get all strikes for this expiration and sort them
            strikes = [float(s) for s in strike_map.keys()]
            strikes.sort()  # Sort ascending for easier iteration
            
            # Filter strikes within our range
            valid_strikes = [s for s in strikes if min_strike <= s <= max_strike]
            
            if len(valid_strikes) < 2:
                continue  # Need at least 2 strikes for a spread
                
            # For each lower strike (lower strike - the one we buy)
            for i, lower_strike in enumerate(valid_strikes):
                # Try different string formats for strike lookup
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
                dte = self._calculate_dte(lower_opt["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue
                    
                lower_bid = lower_opt.get("bid", 0)
                lower_ask = lower_opt.get("ask", 0)
                if lower_bid <= 0 or lower_ask <= 0 or lower_ask < lower_bid:
                    continue
                    
                lower_mid = (lower_bid + lower_ask) / 2
                
                # For each higher strike within max_spread distance
                for higher_strike in valid_strikes[i+1:]:  # Only consider higher strikes
                    spread_width = higher_strike - lower_strike
                    if spread_width > max_spread:
                        continue  # Spread too wide
                        
                    # Try different string formats for higher strike lookup
                    higher_strike_str = None
                    for fmt_strike in [str(higher_strike), str(int(higher_strike)), f"{higher_strike:.1f}"]:
                        if fmt_strike in strike_map:
                            higher_strike_str = fmt_strike
                            break
                    
                    if not higher_strike_str or higher_strike_str not in strike_map:
                        continue
                        
                    higher_opts = strike_map[higher_strike_str]
                    if not higher_opts:
                        continue
                        
                    higher_opt = higher_opts[0]
                    higher_bid = higher_opt.get("bid", 0)
                    higher_ask = higher_opt.get("ask", 0)
                    if higher_bid <= 0 or higher_ask <= 0 or higher_ask < higher_bid:
                        continue
                        
                    higher_mid = (higher_bid + higher_ask) / 2
                    
                    # Validate that higher strike mid > lower strike mid (credit spread)
                    if higher_mid <= lower_mid:
                        continue
                        
                    # Calculate spread metrics
                    credit_received = (higher_mid - lower_mid) * 100  # Net credit received
                    max_risk = (spread_width * 100) - credit_received  # Max loss
                    
                    if credit_received <= 0:
                        continue  # Only profitable spreads
                        
                    # For put credit spreads, max gain is the credit received
                    max_gain = credit_received
                    pct_gain = (max_gain / max_risk) * 100 if max_risk > 0 else 0
                    ann_pct_gain = (pct_gain * 365) / dte if dte > 0 else 0
                    
                    # Calculate strike percentage (higher strike as percentage of current price)
                    strike_pct = (higher_strike / price) * 100
                    
                    exp_ts = int(
                        _dt.datetime.fromisoformat(lower_opt["expirationDate"]).timestamp()
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
                            "higherStrike": higher_strike,
                            "spreadWidth": spread_width,
                            "lowerBid": lower_bid,
                            "lowerAsk": lower_ask,
                            "lowerMid": lower_mid,
                            "higherBid": higher_bid,
                            "higherAsk": higher_ask,
                            "higherMid": higher_mid,
                            "creditReceived": credit_received,
                            "maxRisk": max_risk,
                            "maxGain": max_gain,
                            "pctGain": pct_gain,
                            "annPctGain": ann_pct_gain,
                        }
                    )

        return records, api_calls

    # ------------------------------------------------------------------#
    # NEW – Put-Call Spread strategy                                    #
    # ------------------------------------------------------------------#

    def fetch_put_call_spread_data(
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
        Return profitable put-call spread opportunities for the requested symbols.
        
        Combines both call spread and put spread strategies, returning all results
        from both strategies in a single sorted list.
        """
        records: List[Dict[str, Any]] = []
        api_calls = 0

        for sym in symbols:
            try:
                # Fetch call spread data
                call_recs, call_api_calls = self._fetch_stock_call_spread(
                    symbol=sym,
                    min_strike_pct=min_strike_pct,
                    max_strike_pct=max_strike_pct,
                    min_dte=min_dte,
                    max_dte=max_dte,
                    max_spread=max_spread,
                )
                
                # Add strategy type to call spread records
                for rec in call_recs:
                    rec["strategyType"] = "call_spread"
                
                records.extend(call_recs)
                api_calls += call_api_calls
                
                # Fetch put spread data
                put_recs, put_api_calls = self._fetch_stock_put_spread(
                    symbol=sym,
                    min_strike_pct=min_strike_pct,
                    max_strike_pct=max_strike_pct,
                    min_dte=min_dte,
                    max_dte=max_dte,
                    max_spread=max_spread,
                )
                
                # Add strategy type to put spread records
                for rec in put_recs:
                    rec["strategyType"] = "put_spread"
                
                records.extend(put_recs)
                api_calls += put_api_calls
                
            except SchwabAPIError:
                raise
            except Exception as exc:  # pragma: no cover
                raise SchwabAPIError(f"Error processing {sym}: {exc}") from exc

        # Sort combined results by annualized percentage gain (descending)
        records.sort(key=lambda x: x.get("annPctGain", 0), reverse=True)

        return records, api_calls

    # ------------------------------------------------------------------#
    # NEW – Iron Condor strategy                                        #
    # ------------------------------------------------------------------#

    def fetch_iron_condor_data(
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
        Return profitable iron condor opportunities for the requested symbols.

        An Iron Condor combines a put credit spread (below current price) with
        a call credit spread (above current price) with matching spread widths.

        The strike_pct parameter works symmetrically:
        - For puts: looks at strikes at (100 - pct)% of current price
        - For calls: looks at strikes at (100 + (100 - pct))% of current price

        Example: stock at $100, min_strike_pct=70 means:
        - Put side: 70% of $100 = $70 put
        - Call side: 130% of $100 = $130 call (mirror of 70%)
        """
        records: List[Dict[str, Any]] = []
        api_calls = 0

        for sym in symbols:
            try:
                recs, calls = self._fetch_stock_iron_condor(
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

        # Sort by annualized percentage gain (descending)
        records.sort(key=lambda x: x.get("annPctGain", 0), reverse=True)

        return records, api_calls

    def _fetch_stock_iron_condor(
        self,
        *,
        symbol: str,
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
        max_spread: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return profitable iron condor records for a single underlying."""
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

        # Strike boundaries for PUT side (below current price)
        # min_strike_pct=70 means look at 70% of current price for puts
        put_min_strike = price * (min_strike_pct / 100)
        put_max_strike = price * (max_strike_pct / 100)

        # Strike boundaries for CALL side (above current price - mirror image)
        # min_strike_pct=70 means look at 130% of current price for calls
        call_min_strike = price * (2 - max_strike_pct / 100)  # e.g., 2 - 0.9 = 1.1 = 110%
        call_max_strike = price * (2 - min_strike_pct / 100)  # e.g., 2 - 0.7 = 1.3 = 130%

        # ------------------ 2) Chains (ALL - need both puts and calls) ---#
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        params = {
            "symbol": symbol,
            "contractType": "ALL",
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
        put_map = chain_json.get("putExpDateMap", {})
        call_map = chain_json.get("callExpDateMap", {})

        # Iterate over expirations present in BOTH maps
        for exp_key in put_map:
            if exp_key not in call_map:
                continue

            put_strike_map = put_map[exp_key]
            call_strike_map = call_map[exp_key]

            # Get all put strikes within our range
            put_strikes = [float(s) for s in put_strike_map.keys()]
            put_strikes.sort()  # ascending
            valid_put_strikes = [s for s in put_strikes if put_min_strike <= s <= put_max_strike]

            # Get all call strikes within our range
            call_strikes = [float(s) for s in call_strike_map.keys()]
            call_strikes.sort()  # ascending
            valid_call_strikes = [s for s in call_strikes if call_min_strike <= s <= call_max_strike]

            if len(valid_put_strikes) < 2 or len(valid_call_strikes) < 2:
                continue

            # Build put spreads (credit spreads: sell higher, buy lower)
            put_spreads = []
            for i, lower_put in enumerate(valid_put_strikes):
                lower_put_str = self._find_strike_key(put_strike_map, lower_put)
                if not lower_put_str:
                    continue

                lower_put_opts = put_strike_map[lower_put_str]
                if not lower_put_opts:
                    continue
                lower_put_opt = lower_put_opts[0]

                dte = self._calculate_dte(lower_put_opt["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue

                lower_put_bid = lower_put_opt.get("bid", 0)
                lower_put_ask = lower_put_opt.get("ask", 0)
                if lower_put_bid <= 0 or lower_put_ask <= 0:
                    continue

                for higher_put in valid_put_strikes[i+1:]:
                    spread_width = higher_put - lower_put
                    if spread_width > max_spread:
                        continue

                    higher_put_str = self._find_strike_key(put_strike_map, higher_put)
                    if not higher_put_str:
                        continue

                    higher_put_opts = put_strike_map[higher_put_str]
                    if not higher_put_opts:
                        continue
                    higher_put_opt = higher_put_opts[0]

                    higher_put_bid = higher_put_opt.get("bid", 0)
                    higher_put_ask = higher_put_opt.get("ask", 0)
                    if higher_put_bid <= 0 or higher_put_ask <= 0:
                        continue

                    # Credit spread: sell higher, buy lower
                    if higher_put_bid <= lower_put_ask:
                        continue  # No credit available

                    put_spreads.append({
                        "lowerStrike": lower_put,
                        "higherStrike": higher_put,
                        "spreadWidth": spread_width,
                        "lowerBid": lower_put_bid,
                        "lowerAsk": lower_put_ask,
                        "higherBid": higher_put_bid,
                        "higherAsk": higher_put_ask,
                        "dte": dte,
                        "expDate": lower_put_opt["expirationDate"],
                    })

            # Build call spreads (credit spreads: sell lower, buy higher)
            call_spreads = []
            for i, lower_call in enumerate(valid_call_strikes):
                lower_call_str = self._find_strike_key(call_strike_map, lower_call)
                if not lower_call_str:
                    continue

                lower_call_opts = call_strike_map[lower_call_str]
                if not lower_call_opts:
                    continue
                lower_call_opt = lower_call_opts[0]

                dte = self._calculate_dte(lower_call_opt["expirationDate"])
                if dte < min_dte or dte > max_dte:
                    continue

                lower_call_bid = lower_call_opt.get("bid", 0)
                lower_call_ask = lower_call_opt.get("ask", 0)
                if lower_call_bid <= 0 or lower_call_ask <= 0:
                    continue

                for higher_call in valid_call_strikes[i+1:]:
                    spread_width = higher_call - lower_call
                    if spread_width > max_spread:
                        continue

                    higher_call_str = self._find_strike_key(call_strike_map, higher_call)
                    if not higher_call_str:
                        continue

                    higher_call_opts = call_strike_map[higher_call_str]
                    if not higher_call_opts:
                        continue
                    higher_call_opt = higher_call_opts[0]

                    higher_call_bid = higher_call_opt.get("bid", 0)
                    higher_call_ask = higher_call_opt.get("ask", 0)
                    if higher_call_bid <= 0 or higher_call_ask <= 0:
                        continue

                    # Credit spread: sell lower, buy higher
                    if lower_call_bid <= higher_call_ask:
                        continue  # No credit available

                    call_spreads.append({
                        "lowerStrike": lower_call,
                        "higherStrike": higher_call,
                        "spreadWidth": spread_width,
                        "lowerBid": lower_call_bid,
                        "lowerAsk": lower_call_ask,
                        "higherBid": higher_call_bid,
                        "higherAsk": higher_call_ask,
                        "dte": dte,
                        "expDate": lower_call_opt["expirationDate"],
                    })

            # Combine put spreads with call spreads of MATCHING width
            for put_spread in put_spreads:
                for call_spread in call_spreads:
                    # Must have same spread width and same expiration
                    if put_spread["spreadWidth"] != call_spread["spreadWidth"]:
                        continue
                    if put_spread["dte"] != call_spread["dte"]:
                        continue

                    spread_width = put_spread["spreadWidth"]
                    dte = put_spread["dte"]

                    # Calculate combined metrics using mid prices
                    put_lower_mid = (put_spread["lowerBid"] + put_spread["lowerAsk"]) / 2
                    put_higher_mid = (put_spread["higherBid"] + put_spread["higherAsk"]) / 2
                    call_lower_mid = (call_spread["lowerBid"] + call_spread["lowerAsk"]) / 2
                    call_higher_mid = (call_spread["higherBid"] + call_spread["higherAsk"]) / 2

                    # Put credit = sell higher put - buy lower put
                    put_credit = (put_higher_mid - put_lower_mid) * 100
                    # Call credit = sell lower call - buy higher call
                    call_credit = (call_lower_mid - call_higher_mid) * 100

                    total_credit = put_credit + call_credit

                    if total_credit <= 0:
                        continue  # Only profitable iron condors

                    # Max risk = spread width * 100 - total credit
                    max_risk = (spread_width * 100) - total_credit

                    if max_risk <= 0:
                        continue

                    pct_gain = (total_credit / max_risk) * 100
                    ann_pct_gain = (pct_gain * 365) / dte if dte > 0 else 0

                    # Strike percentages relative to current price
                    put_strike_pct = (put_spread["higherStrike"] / price) * 100
                    call_strike_pct = (call_spread["lowerStrike"] / price) * 100

                    exp_ts = int(
                        _dt.datetime.fromisoformat(put_spread["expDate"]).timestamp()
                    )

                    records.append({
                        "symbol": symbol,
                        "price": price,
                        "exp": exp_ts,
                        "expDate": _dt.datetime.fromtimestamp(exp_ts).strftime("%d/%m/%Y"),
                        "dte": dte,
                        "spreadWidth": spread_width,
                        # Put side
                        "putLowerStrike": put_spread["lowerStrike"],
                        "putHigherStrike": put_spread["higherStrike"],
                        "putStrikePct": put_strike_pct,
                        "putLowerBid": put_spread["lowerBid"],
                        "putLowerAsk": put_spread["lowerAsk"],
                        "putLowerMid": put_lower_mid,
                        "putHigherBid": put_spread["higherBid"],
                        "putHigherAsk": put_spread["higherAsk"],
                        "putHigherMid": put_higher_mid,
                        "putCredit": put_credit,
                        # Call side
                        "callLowerStrike": call_spread["lowerStrike"],
                        "callHigherStrike": call_spread["higherStrike"],
                        "callStrikePct": call_strike_pct,
                        "callLowerBid": call_spread["lowerBid"],
                        "callLowerAsk": call_spread["lowerAsk"],
                        "callLowerMid": call_lower_mid,
                        "callHigherBid": call_spread["higherBid"],
                        "callHigherAsk": call_spread["higherAsk"],
                        "callHigherMid": call_higher_mid,
                        "callCredit": call_credit,
                        # Combined metrics
                        "totalCredit": total_credit,
                        "maxRisk": max_risk,
                        "pctGain": pct_gain,
                        "annPctGain": ann_pct_gain,
                    })

        return records, api_calls

    def _find_strike_key(self, strike_map: Dict, strike: float) -> str | None:
        """Find the correct string key for a strike in the strike map."""
        for fmt in [str(strike), str(int(strike)), f"{strike:.1f}"]:
            if fmt in strike_map:
                return fmt
        return None

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
