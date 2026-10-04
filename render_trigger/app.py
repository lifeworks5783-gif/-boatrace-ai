import os
import time
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "lifeworks5783-gif")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "-boatrace-ai")
TRIGGER_PATH = os.environ.get("TRIGGER_PATH", "config/run_family_full_refresh_now.txt")
ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN",
    "https://lifeworks5783-gif.github.io",
)

def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.after_request
def add_cors_headers(resp):
    return cors(resp)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/trigger", methods=["OPTIONS"])
def trigger_options():
    return ("", 204)

@app.route("/trigger", methods=["POST"])
def trigger():
    origin = request.headers.get("Origin")
    if origin and origin != ALLOWED_ORIGIN:
        return jsonify({"ok": False, "error": "origin_not_allowed"}), 403

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{TRIGGER_PATH}"

    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return jsonify({"ok": False, "error": "trigger_file_read_failed"}), 502

    meta = r.json()
    payload = {
        "message": "Trigger Fast Live V3 from family page",
        "content": __import__("base64").b64encode(
            f"family page trigger\nrequested_unix={int(time.time())}\n".encode()
        ).decode(),
        "sha": meta["sha"],
        "branch": "main",
    }

    u = requests.put(url, headers=headers, json=payload, timeout=15)
    if u.status_code not in (200, 201):
        return jsonify({"ok": False, "error": "trigger_file_update_failed"}), 502

    return jsonify({"ok": True, "message": "update_started"}), 202
