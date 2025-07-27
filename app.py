from __future__ import annotations

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

if __name__ == "__main__":
    # Only reachable locally
    app.run(host="127.0.0.1", port=5000, debug=True)
