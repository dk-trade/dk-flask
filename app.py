from __future__ import annotations

"""
Flask entry‑point for the secured local version of the Covered‑Call helper.

Key points
----------
* Credentials are **never** exposed to the browser; they are read from `.env`.
* Browser sends only filter parameters (symbols, strike range, DTE range).
* All Schwab API traffic and token management are handled server‑side via
  the helper class defined in `schwab_api.py`.
* The server returns pre‑filtered option records as JSON that the existing
  front‑end can render.
"""

import json
import os
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Local helper that wraps Schwab OAuth + option chain logic
from schwab_api import SchwabAPI, SchwabAPIError

load_dotenv()  # reads .env in project root

# ---------------------------------------------------------------------------
# Configuration & initialisation
# ---------------------------------------------------------------------------

# Credentials live ONLY on the server
CLIENT_ID: str | None = os.getenv("SCHWAB_APP_KEY")
CLIENT_SECRET: str | None = os.getenv("SCHWAB_APP_SECRET")
REFRESH_TOKEN: str | None = os.getenv("SCHWAB_REFRESH_TOKEN")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
    raise RuntimeError("Missing Schwab credentials. Please set SCHWAB_CLIENT_ID, "
                       "SCHWAB_CLIENT_SECRET and SCHWAB_REFRESH_TOKEN in your .env file.")

# Create a single SchwabAPI instance for the lifetime of the app
schwab_api = SchwabAPI(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
)

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Return the main HTML page."""
    # Jinja template simply pulls scripts/styles from the static folder.
    return render_template("index.html")


@app.route("/api/fetch-options", methods=["POST"])
def fetch_options():
    """Compute eligible covered‑call options for requested symbols.

    Request JSON example::
        {
          "symbols": ["AAPL", "MSFT"],
          "minStrikePct": 30,
          "maxStrikePct": 80,
          "minDte": 1,
          "maxDte": 45
        }
    """
    try:
        data = request.get_json(force=True)  # auto 400 if invalid JSON
    except Exception as exc:
        return jsonify({"error": f"Invalid JSON payload: {exc}"}), 400

    # Basic validation -------------------------------------------------------
    required_fields = {"symbols", "minStrikePct", "maxStrikePct", "minDte", "maxDte"}
    if not required_fields.issubset(data):
        return jsonify({"error": f"Request must include keys: {sorted(required_fields)}"}), 400

    symbols = [s.upper() for s in data["symbols"] if isinstance(s, str) and s.strip()]
    if not symbols:
        return jsonify({"error": "At least one symbol is required."}), 400

    try:
        min_strike_pct = int(data["minStrikePct"])
        max_strike_pct = int(data["maxStrikePct"])
        min_dte = int(data["minDte"])
        max_dte = int(data["maxDte"])
    except (ValueError, TypeError):
        return jsonify({"error": "Strike percentages and DTE values must be integers."}), 400

    # Call Schwab API helper --------------------------------------------------
    try:
        records, api_calls = schwab_api.fetch_options_data(
            symbols=symbols,
            min_strike_pct=min_strike_pct,
            max_strike_pct=max_strike_pct,
            min_dte=min_dte,
            max_dte=max_dte,
        )
    except SchwabAPIError as exc:
        return jsonify({"error": str(exc)}), 502  # Bad Gateway – upstream failure

    return jsonify({"records": records, "apiCalls": api_calls})  # 200 OK


# ---------------------------------------------------------------------------
# Local entry‑point (run with `python app.py`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Default to 127.0.0.1 so it is only reachable locally.
    app.run(host="127.0.0.1", port=5000, debug=True)
