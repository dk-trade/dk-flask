from __future__ import annotations
import webbrowser
import json
import base64  # if not already imported
import requests
import secrets
import urllib.parse

"""
app.py – Flask entry-point for the secured local options-strategy helper.

Now supports **three** strategies:

* Covered-Call  → served at `/covered-call`    | API: `/api/fetch-options`
* Collar        → served at `/collar`          | API: `/api/fetch-collar`
* Call Spread   → served at `/call-spread`     | API: `/api/fetch-call-spread`

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
    """Common JSON schema for strategies; raises `ValueError` on issues."""
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

    result = {
        "symbols": symbols,
        "min_strike_pct": min_strike_pct,
        "max_strike_pct": max_strike_pct,
        "min_dte": min_dte,
        "max_dte": max_dte,
    }
    
    # Handle max_spread parameter for call spread strategy
    if "maxSpread" in data:
        try:
            result["max_spread"] = int(data["maxSpread"])
            if result["max_spread"] < 1 or result["max_spread"] > 30:
                raise ValueError("Max spread must be between 1 and 30.")
        except (TypeError, ValueError) as e:
            if "must be between" in str(e):
                raise e
            raise ValueError("Max spread must be an integer.")
    
    return result


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


@app.route("/call-spread")
def call_spread_page():
    return render_template("call_spread.html")


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


@app.route("/api/fetch-call-spread", methods=["POST"])
def fetch_call_spread():
    """Call spread strategy endpoint."""
    try:
        payload = _parse_payload(request.get_json(force=True))
        records, api_calls = schwab_api.fetch_call_spread_data(**payload)
        return jsonify({"records": records, "apiCalls": api_calls})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502


# --------------------------------------------------------------------------- #
# OAuth Token Refresh                                                         #
# --------------------------------------------------------------------------- #


@app.route("/start-token-refresh")
def start_token_refresh():
    """Start the OAuth flow for token refresh."""
    global oauth_state
    oauth_state = secrets.token_urlsafe(16)

    # Build authorization URL (HTTPS redirect URI like original working script)
    base_url = "https://api.schwabapi.com/v1/oauth/authorize"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": "https://127.0.0.1:8182/callback",  # Changed to HTTPS and /callback
        "scope": "marketdata.quote",
        "state": oauth_state,
    }
    auth_url = f"{base_url}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


@app.route("/callback")  # Changed from /oauth-callback to /callback
def oauth_callback():
    """Handle OAuth callback and exchange code for tokens."""
    global new_refresh_token

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    print("From callback:")
    print(f"Code: {code}")
    print(f"State: {state}")
    print("==============")

    if error:
        return f"OAuth error: {error}", 400

    if state != oauth_state:
        return "Invalid state. CSRF detected.", 400

    # Exchange code for tokens synchronously (not in thread)
    success = exchange_code_for_token(code)
    
    if success:
        # Redirect to main page with success parameter
        return redirect(url_for("root") + "?token_success=1")
    else:
        return "Failed to exchange code for token. Please try again.", 500


def exchange_code_for_token(code):
    """Exchange authorization code for tokens (using original working method)."""
    global new_refresh_token, schwab_api
    
    print("[*] Exchanging authorization code for tokens...")
    token_url = "https://api.schwabapi.com/v1/oauth/token"

    # Use the same auth method as the working original script
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": "Basic "
        + requests.auth._basic_auth_str(CLIENT_ID, CLIENT_SECRET).split(" ")[1],
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://127.0.0.1:8182/callback",  # Match the redirect URI
    }

    try:
        response = requests.post(token_url, headers=headers, data=data, verify=True, timeout=30)

        if response.status_code == 200:
            token_data = response.json()
            new_refresh_token = token_data.get("refresh_token")

            # Print to console
            print(f"\n{'='*50}")
            print("NEW REFRESH TOKEN OBTAINED:")
            print(f"SCHWAB_REFRESH_TOKEN={new_refresh_token}")
            print(f"{'='*50}\n")
            print("[✔] Token response:")
            print(token_data)

            # Auto-update .env file
            update_env_file(new_refresh_token)
            
            # Update the SchwabAPI instance with new token
            schwab_api.refresh_token = new_refresh_token
            
            return True

        else:
            print(f"[✘] Failed to get token: {response.status_code}")
            print(response.text)
            return False

    except Exception as e:
        print(f"Error during token exchange: {e}")
        return False


def update_env_file(new_token):
    """Update the .env file with the new refresh token."""
    try:
        env_path = Path(".env")
        if env_path.exists():
            # Read current .env content
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update the SCHWAB_REFRESH_TOKEN line
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith('SCHWAB_REFRESH_TOKEN='):
                    lines[i] = f'SCHWAB_REFRESH_TOKEN="{new_token}"\n'  # Added quotes
                    updated = True
                    break
            
            # If not found, append it
            if not updated:
                lines.append(f'SCHWAB_REFRESH_TOKEN="{new_token}"\n')  # Added quotes
            
            # Write back to .env
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            print(f"[✔] Updated .env file with new refresh token")
            
        else:
            print(f"[!] .env file not found, creating new one")
            with open(env_path, 'w') as f:
                f.write(f'SCHWAB_REFRESH_TOKEN="{new_token}"\n')  # Added quotes
                
    except Exception as e:
        print(f"[✘] Failed to update .env file: {e}")
        print(f"[!] Please manually update SCHWAB_REFRESH_TOKEN=\"{new_token}\"")


@app.route("/get-new-token")
def get_new_token():
    """API endpoint to get the new refresh token."""
    global new_refresh_token
    if new_refresh_token:
        return jsonify({"token": new_refresh_token})
    return jsonify({"token": None})


# --------------------------------------------------------------------------- #
# Local entry-point                                                           #
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    # Always open browser (remove IS_DEV check)
    # webbrowser.open("https://127.0.0.1:8182")

    # Run with HTTPS like the original working script
    app.run(host="127.0.0.1", port=8182, ssl_context="adhoc", debug=True)