from __future__ import annotations
import webbrowser
import json
import base64  # if not already imported
import requests
import secrets
import urllib.parse
import threading

"""
app.py – Flask entry-point for the secured local options-strategy helper.

Now supports **two** strategies:

* Covered-Call  → served at `/covered-call`  | API: `/api/fetch-options`
* Collar        → served at `/collar`        | API: `/api/fetch-collar`

`/` shows a landing page where the user can choose the desired strategy.
All Schwab credentials remain on the server and are loaded from `.env`.
"""
import os
from pathlib import Path
from typing import Dict, Any, List

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
)
from dotenv import load_dotenv

from schwab_api import SchwabAPI, SchwabAPIError

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

load_dotenv()  # read .env in project root

CLIENT_ID: str | None = os.getenv("SCHWAB_APP_KEY")
CLIENT_SECRET: str | None = os.getenv("SCHWAB_APP_SECRET")
REFRESH_TOKEN: str | None = os.getenv("SCHWAB_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    raise RuntimeError(
        "Missing Schwab credentials. Please set SCHWAB_APP_KEY, "
        "SCHWAB_APP_SECRET and SCHWAB_REFRESH_TOKEN in your .env file."
    )

# Single SchwabAPI instance for entire app
schwab_api = SchwabAPI(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
)

oauth_state = None
new_refresh_token = None

app = Flask(__name__, static_folder="static", template_folder="templates")

# --------------------------------------------------------------------------- #
# Helper – shared payload validation                                          #
# --------------------------------------------------------------------------- #


def _parse_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Common JSON schema for both strategies; raises `ValueError` on issues."""
    required = {"symbols", "minStrikePct", "maxStrikePct", "minDte", "maxDte"}
    if not required.issubset(data):
        raise ValueError(f"Payload must include keys: {sorted(required)}")

    symbols = [s.upper() for s in data["symbols"] if isinstance(s, str) and s.strip()]
    if not symbols:
        raise ValueError("At least one symbol is required.")

    try:
        min_strike_pct = int(data["minStrikePct"])
        max_strike_pct = int(data["maxStrikePct"])
        min_dte = int(data["minDte"])
        max_dte = int(data["maxDte"])
    except (TypeError, ValueError):
        raise ValueError("Strike percentages and DTE values must be integers.")

    return {
        "symbols": symbols,
        "min_strike_pct": min_strike_pct,
        "max_strike_pct": max_strike_pct,
        "min_dte": min_dte,
        "max_dte": max_dte,
    }


# --------------------------------------------------------------------------- #
# UI routes                                                                   #
# --------------------------------------------------------------------------- #


@app.route("/")
def root():
    """Landing page – lets the user choose a strategy."""
    return render_template("index.html")


@app.route("/covered-call")
def covered_call_page():
    return render_template("covered_call.html")


@app.route("/api/symbols")
def list_symbols():
    fp = Path(__file__).with_name("stock_symbols_full.json")
    with open(fp) as f:
        return jsonify(json.load(f))


@app.route("/collar")
def collar_page():
    return render_template("collar.html")


# --------------------------------------------------------------------------- #
# API routes                                                                  #
# --------------------------------------------------------------------------- #


@app.route("/api/fetch-options", methods=["POST"])
def fetch_options():
    """Covered-call endpoint (existing behaviour)."""
    try:
        payload = _parse_payload(request.get_json(force=True))
        records, api_calls = schwab_api.fetch_options_data(**payload)
        return jsonify({"records": records, "apiCalls": api_calls})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/fetch-collar", methods=["POST"])
def fetch_collar():
    """Collar strategy endpoint."""
    try:
        payload = _parse_payload(request.get_json(force=True))
        records, api_calls = schwab_api.fetch_collar_data(**payload)
        return jsonify({"records": records, "apiCalls": api_calls})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502


# --------------------------------------------------------------------------- #
# Local entry-point                                                           #
# --------------------------------------------------------------------------- #



@app.route("/start-token-refresh")
def start_token_refresh():
    """Start the OAuth flow for token refresh."""
    global oauth_state
    oauth_state = secrets.token_urlsafe(16)

    # Build authorization URL (redirect to main app port)
    base_url = "https://api.schwabapi.com/v1/oauth/authorize"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": "http://127.0.0.1:8182/oauth-callback",  # Main app port
        "scope": "marketdata.quote",
        "state": oauth_state,
    }
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


@app.route("/oauth-callback")
def oauth_callback():
    """Handle OAuth callback and exchange code for tokens."""
    global new_refresh_token

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"OAuth error: {error}", 400

    if state != oauth_state:
        return "Invalid state. CSRF detected.", 400

    # Exchange code for tokens
    try:
        token_url = "https://api.schwabapi.com/v1/oauth/token"

        creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
        auth_header = base64.b64encode(creds.encode()).decode()

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}",
        }

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://127.0.0.1:8182/oauth-callback",
        }

        response = requests.post(token_url, headers=headers, data=data, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            new_refresh_token = token_data.get("refresh_token")

            # Print to console
            print(f"\n{'='*50}")
            print("NEW REFRESH TOKEN OBTAINED:")
            print(f"SCHWAB_REFRESH_TOKEN={new_refresh_token}")
            print(f"{'='*50}\n")

            return redirect(url_for("root") + "?token_success=1")
        else:
            print(f"Token exchange failed: {response.status_code}")
            print(response.text)
            return f"Token exchange failed: {response.status_code}", 400

    except Exception as e:
        print(f"Error during token exchange: {e}")
        return f"Error during token exchange: {e}", 500


@app.route("/get-new-token")
def get_new_token():
    """API endpoint to get the new refresh token."""
    global new_refresh_token
    if new_refresh_token:
        return jsonify({"token": new_refresh_token})
    return jsonify({"token": None})


if __name__ == "__main__":

    if not os.getenv("IS_DEV"):
        webbrowser.open("http://127.0.0.1:8182")

    app.run(host="127.0.0.1", port=8182, debug=True)
