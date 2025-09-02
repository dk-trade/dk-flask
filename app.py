from __future__ import annotations
import webbrowser
import json
import base64  # if not already imported
import requests
import secrets
import urllib.parse

"""
app.py – Flask entry-point for the secured local options-strategy helper.

Now supports **five** strategies:

* Covered-Call     → served at `/covered-call`       | API: `/api/fetch-options`
* Collar           → served at `/collar`             | API: `/api/fetch-collar`
* Call Spread      → served at `/call-spread`        | API: `/api/fetch-call-spread`
* Put Spread       → served at `/put-spread`         | API: `/api/fetch-put-spread`
* Put-Call-Spread  → served at `/put-call-spread`    | API: `/api/fetch-put-call-spread`

`/` shows a landing page where the user can choose the desired strategy.
All Schwab credentials remain on the server and are loaded from `.env`.
"""
import os
import datetime as _dt
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


@app.route("/put-spread")
def put_spread_page():
    return render_template("put_spread.html")


@app.route("/put-call-spread")
def put_call_spread_page():
    return render_template("put_call_spread.html")


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


@app.route("/api/fetch-put-spread", methods=["POST"])
def fetch_put_spread():
    """Put spread strategy endpoint."""
    try:
        payload = _parse_payload(request.get_json(force=True))
        records, api_calls = schwab_api.fetch_put_spread_data(**payload)
        return jsonify({"records": records, "apiCalls": api_calls})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/fetch-put-call-spread", methods=["POST"])
def fetch_put_call_spread():
    """Put-call spread strategy endpoint - combines both put and call spreads."""
    try:
        payload = _parse_payload(request.get_json(force=True))
        records, api_calls = schwab_api.fetch_put_call_spread_data(**payload)
        return jsonify({"records": records, "apiCalls": api_calls})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502


# --------------------------------------------------------------------------- #
# Stock Configuration Management                                               #
# --------------------------------------------------------------------------- #


@app.route("/api/config/put-call-spread", methods=["GET"])
def get_put_call_spread_config():
    """Get the put-call-spread stock configuration."""
    try:
        config_path = Path(__file__).with_name("stock_config_jsons") / "put_call_spread.json"
        if not config_path.exists():
            # Return default config if file doesn't exist
            default_config = {
                "name": "My Put-Call Spreads",
                "description": "Combined put and call spread opportunities",
                "lastUpdated": _dt.datetime.utcnow().isoformat() + "Z",
                "defaultParams": {
                    "minStrikePct": 30,
                    "maxStrikePct": 90,
                    "minDte": 30,
                    "maxDte": 90,
                    "maxSpread": 20
                },
                "stocks": []
            }
            return jsonify(default_config)
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({"error": f"Failed to load config: {str(e)}"}), 500


@app.route("/api/config/put-call-spread", methods=["POST"])
def save_put_call_spread_config():
    """Save the put-call-spread stock configuration."""
    try:
        config = request.get_json(force=True)
        
        # Validate config structure
        required_fields = ["name", "defaultParams", "stocks"]
        if not all(field in config for field in required_fields):
            return jsonify({"error": "Invalid config structure"}), 400
            
        # Validate default params
        default_params = config["defaultParams"]
        required_params = ["minStrikePct", "maxStrikePct", "minDte", "maxDte", "maxSpread"]
        if not all(param in default_params for param in required_params):
            return jsonify({"error": "Invalid default parameters"}), 400
            
        # Update lastUpdated timestamp
        config["lastUpdated"] = _dt.datetime.utcnow().isoformat() + "Z"
        
        # Ensure directory exists
        config_dir = Path(__file__).with_name("stock_config_jsons")
        config_dir.mkdir(exist_ok=True)
        
        config_path = config_dir / "put_call_spread.json"
        
        # Create backup of existing config
        if config_path.exists():
            backup_path = config_path.with_suffix('.json.backup')
            config_path.replace(backup_path)
            
        # Save new config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
        return jsonify({"success": True, "message": "Configuration saved successfully"})
    except Exception as e:
        return jsonify({"error": f"Failed to save config: {str(e)}"}), 500


@app.route("/api/batch-run/put-call-spread", methods=["POST"])
def batch_run_put_call_spread():
    """Execute put-call-spread strategy for all enabled stocks in config."""
    try:
        # Load config
        config_path = Path(__file__).with_name("stock_config_jsons") / "put_call_spread.json"
        if not config_path.exists():
            return jsonify({"error": "No configuration file found"}), 404
            
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        enabled_stocks = [stock for stock in config["stocks"] if stock.get("enabled", True)]
        if not enabled_stocks:
            return jsonify({"error": "No enabled stocks in configuration"}), 400
            
        all_records = []
        total_api_calls = 0
        results_summary = {
            "total_stocks": len(enabled_stocks),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for stock in enabled_stocks:
            try:
                # Use stock-specific parameters
                payload = {
                    "symbols": [stock["symbol"]],
                    "min_strike_pct": stock.get("minStrikePct", config["defaultParams"]["minStrikePct"]),
                    "max_strike_pct": stock.get("maxStrikePct", config["defaultParams"]["maxStrikePct"]), 
                    "min_dte": stock.get("minDte", config["defaultParams"]["minDte"]),
                    "max_dte": stock.get("maxDte", config["defaultParams"]["maxDte"]),
                    "max_spread": stock.get("maxSpread", config["defaultParams"]["maxSpread"])
                }
                
                records, api_calls = schwab_api.fetch_put_call_spread_data(**payload)
                
                # Add stock notes to each record
                for record in records:
                    if stock.get("notes"):
                        record["stockNotes"] = stock["notes"]
                        
                all_records.extend(records)
                total_api_calls += api_calls
                results_summary["successful"] += 1
                
            except Exception as e:
                results_summary["failed"] += 1
                results_summary["errors"].append({
                    "symbol": stock["symbol"],
                    "error": str(e)
                })
        
        # Sort all records by annualized percentage gain
        all_records.sort(key=lambda x: x.get("annPctGain", 0), reverse=True)
        
        return jsonify({
            "records": all_records,
            "apiCalls": total_api_calls,
            "summary": results_summary
        })
        
    except Exception as e:
        return jsonify({"error": f"Batch execution failed: {str(e)}"}), 500


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
    webbrowser.open("https://127.0.0.1:8182")

    # Run with HTTPS like the original working script
    app.run(host="127.0.0.1", port=8182, ssl_context="adhoc", debug=True)