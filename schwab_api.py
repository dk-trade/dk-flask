from __future__ import annotations

"""schwab_api.py – Thin wrapper around Schwab OAuth and option‑chain endpoints.

This file **never** exposes credentials to the caller.  All token handling is
internal.  Public surface consists of:

* ``SchwabAPI.fetch_options_data(...)`` – Bulk fetch and filtering helper that
  matches the original JS logic.

Raise ``SchwabAPIError`` on any recoverable problem so the Flask route can
convert it to a proper HTTP response.
"""

import base64
import datetime as _dt
import os
from typing import Any, Dict, List, Tuple

import requests
from dotenv import load_dotenv

__all__ = [
    "SchwabAPI",
    "SchwabAPIError",
]


class SchwabAPIError(RuntimeError):
    """Custom exception raised for any Schwab API–related error."""


class SchwabAPI:
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
    QUOTES_URL = "https://api.schwabapi.com/marketdata/v1/quotes"
    CHAINS_URL = "https://api.schwabapi.com/marketdata/v1/chains"

    def __init__(self, *, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token

        self._access_token: str | None = None
        self._token_expiry: _dt.datetime | None = None

        # Lazily refresh when first needed – avoids network hit on app start.

    # ---------------------------------------------------------------------
    # Token management
    # ---------------------------------------------------------------------

    def _valid_access_token(self) -> str:
        if self._access_token and self._token_expiry and _dt.datetime.utcnow() < self._token_expiry - _dt.timedelta(seconds=60):
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
            raise SchwabAPIError(f"Token refresh failed: {resp.status_code} {resp.text}")

        payload = resp.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 1800))
        self._token_expiry = _dt.datetime.utcnow() + _dt.timedelta(seconds=expires_in)
        if "refresh_token" in payload:
            # In practice Schwab _can_ rotate refresh tokens – store the new one so
            # the next run still works (optional persistence).
            self._refresh_token = payload["refresh_token"]
        return self._access_token

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def fetch_options_data(
        self,
        *,
        symbols: List[str],
        min_strike_pct: int,
        max_strike_pct: int,
        min_dte: int,
        max_dte: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Return list of eligible option records and number of upstream API calls."""

        records: List[Dict[str, Any]] = []
        api_calls = 0
        for symbol in symbols:
            try:
                symbol_records, symbol_calls = self._fetch_stock_options(
                    symbol=symbol,
                    min_strike_pct=min_strike_pct,
                    max_strike_pct=max_strike_pct,
                    min_dte=min_dte,
                    max_dte=max_dte,
                )
                records.extend(symbol_records)
                api_calls += symbol_calls
            except SchwabAPIError:
                raise  # bubble up – caller decides how to handle
            except Exception as exc:
                # Non‑API exception; wrap so caller has consistent handling.
                raise SchwabAPIError(f"Error processing {symbol}: {exc}") from exc

        return records, api_calls

    # ------------------------------------------------------------------
    # Internal per‑symbol logic (mirrors original JS)
    # ------------------------------------------------------------------

    def _fetch_stock_options(
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

        headers = self._auth_headers(json_req=True)

        # 1) Quote -----------------------------------------------------------
        quote_resp = requests.post(
            self.QUOTES_URL,
            headers=headers,
            json={"symbols": [symbol]},
            timeout=30,
        )
        api_calls += 1
        if quote_resp.status_code != 200:
            raise SchwabAPIError(f"Quote fetch failed for {symbol}: {quote_resp.status_code}")

        quote_json = quote_resp.json()
        if symbol not in quote_json:
            raise SchwabAPIError(f"No quote data returned for {symbol}")

        quote_data = quote_json[symbol]["quote"]
        price = quote_data.get("lastPrice") or quote_data.get("mark")
        if price is None:
            raise SchwabAPIError(f"No price available for {symbol}")

        # 2) Date range for option chain -------------------------------------
        today = _dt.date.today()
        from_date = today + _dt.timedelta(days=min_dte)
        to_date = today + _dt.timedelta(days=max_dte)

        # 3) Option chain -----------------------------------------------------
        chain_params = {
            "symbol": symbol,
            "contractType": "CALL",
            "fromDate": from_date.isoformat(),
            "toDate": to_date.isoformat(),
        }
        chain_headers = self._auth_headers(json_req=False)
        chain_resp = requests.get(self.CHAINS_URL, params=chain_params, headers=chain_headers, timeout=30)
        api_calls += 1
        if chain_resp.status_code != 200:
            raise SchwabAPIError(f"Chain fetch failed for {symbol}: {chain_resp.status_code}")

        chain_json = chain_resp.json()
        exp_map = chain_json.get("callExpDateMap", {})

        min_strike = int(price * (min_strike_pct / 100))
        max_strike = int(price * (max_strike_pct / 100))

        for exp_key, strike_map in exp_map.items():
            for strike_str, options_arr in strike_map.items():
                strike = float(strike_str)
                if strike < min_strike or strike > max_strike:
                    continue
                for option in options_arr:
                    dte = self._calculate_dte(option["expirationDate"])
                    if dte < min_dte or dte > max_dte:
                        continue

                    bid = option.get("bid", 0) or 0
                    ask = option.get("ask", 0) or 0
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

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _auth_headers(self, *, json_req: bool) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._valid_access_token()}",
            "Accept": "application/json",
        }
        if json_req:
            headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def _calculate_dte(expiration_iso: str) -> int:
        """Return *calendar* days until expiration (inclusive of today)."""
        exp_date = _dt.datetime.fromisoformat(expiration_iso).date()
        return (exp_date - _dt.date.today()).days

    @staticmethod
    def _calculate_metrics(price: float, strike: float, bid: float, ask: float, dte: int, pct: int = 50) -> Dict[str, float]:
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
