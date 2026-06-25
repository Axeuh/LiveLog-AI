#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Behavior Verification Script

Usage:
    python behavior/verify.py --record       # Record new snapshots
    python behavior/verify.py                 # Verify against existing snapshots
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ============================================================
# Configuration
# ============================================================

CFG = {
    "port": 8769,
    "host": "127.0.0.1",
    "base_url": "http://127.0.0.1:8769",
}
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
PYTHON_PATH = r"D:\ProgramData\miniconda3\envs\axeuh-multi-agent\python.exe"


def _rebuild_url():
    """Rebuild base_url from current port/host."""
    CFG["base_url"] = f"http://{CFG['host']}:{CFG['port']}"


_rebuild_url()

# ============================================================
# Endpoint Definitions
# ============================================================

ENDPOINTS = [
    {
        "method": "GET",
        "path": "/health",
        "body": None,
        "headers": {},
        "note": "Health check endpoint",
        "file_slug": "health",
    },
    {
        "method": "POST",
        "path": "/login",
        "body": {"username": "Axeuh", "password": "20071011"},
        "headers": {},
        "note": "Login success (returns token)",
        "file_slug": "login",
    },
    {
        "method": "POST",
        "path": "/login",
        "body": {"username": "Axeuh", "password": "wrong"},
        "headers": {},
        "note": "Login failure (wrong password)",
        "file_slug": "login_fail",
    },
    {
        "method": "POST",
        "path": "/logout",
        "body": None,
        "headers": {},
        "note": "Logout endpoint",
        "file_slug": "logout",
    },
    {
        "method": "GET",
        "path": "/auth/check",
        "body": None,
        "headers": {},
        "note": "Auth check with token",
        "file_slug": "auth_check",
        "needs_auth": True,
    },
    {
        "method": "GET",
        "path": "/api/screen/tasks",
        "body": None,
        "headers": {},
        "note": "List scheduled tasks",
        "file_slug": "tasks_list",
    },
    {
        "method": "GET",
        "path": "/api/health/dates",
        "body": None,
        "headers": {},
        "note": "List dates with health data",
        "file_slug": "health_dates",
    },
    {
        "method": "GET",
        "path": "/api/health/query?date=2026-06-20",
        "body": None,
        "headers": {},
        "note": "Query health data for a date",
        "file_slug": "health_query",
    },
    {
        "method": "POST",
        "path": "/api/notification/send",
        "body": {"title": "Test", "content": "Hello"},
        "headers": {"Content-Type": "application/json"},
        "note": "Send a notification",
        "file_slug": "notification_send",
    },
    {
        "method": "GET",
        "path": "/api/notification/poll",
        "body": None,
        "headers": {},
        "note": "Poll pending notifications",
        "file_slug": "notification_poll",
    },
    {
        "method": "GET",
        "path": "/api/ota/check?version=1",
        "body": None,
        "headers": {},
        "note": "OTA update check",
        "file_slug": "ota_check",
    },
    {
        "method": "GET",
        "path": "/api/screen/speakers",
        "body": None,
        "headers": {},
        "note": "List registered voiceprints",
        "file_slug": "speakers_list",
    },
    {
        "method": "GET",
        "path": "/api/mobile/files",
        "body": None,
        "headers": {},
        "note": "Browse mobile files",
        "file_slug": "mobile_files",
    },
    {
        "method": "GET",
        "path": "/api/screen/session/list",
        "body": None,
        "headers": {},
        "note": "List all sessions",
        "file_slug": "session_list",
        "needs_auth": True,
    },
    {
        "method": "POST",
        "path": "/api/screen/tts/synthesize",
        "body": {"text": "hello"},
        "headers": {"Content-Type": "application/json"},
        "note": "TTS synthesize (request only, may error without API)",
        "file_slug": "tts_synthesize",
    },
    {
        "method": "GET",
        "path": "/api/screen/model",
        "body": None,
        "headers": {},
        "note": "List available AI models",
        "file_slug": "models",
    },
    {
        "method": "GET",
        "path": "/api/agents/list",
        "body": None,
        "headers": {},
        "note": "List registered remote agents",
        "file_slug": "agents_list",
    },
]

SNAPSHOT_FILES = {
    ep["file_slug"]: SNAPSHOT_DIR / f"{ep['file_slug']}.{ep['method'].lower()}.json"
    for ep in ENDPOINTS
}


# ============================================================
# Helper Functions
# ============================================================


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_request(method, path, body=None, headers=None, auth_token=None):
    """Make an HTTP request to the server."""
    url = f"{CFG['base_url']}{path}"
    req_headers = dict(headers or {})
    if auth_token:
        req_headers["Authorization"] = f"Bearer {auth_token}"

    try:
        if method == "GET":
            resp = requests.get(url, headers=req_headers, timeout=10)
        elif method == "POST":
            if body is not None and "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
            resp = requests.post(url, json=body, headers=req_headers, timeout=30)
        elif method == "PUT":
            if body is not None and "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
            resp = requests.put(url, json=body, headers=req_headers, timeout=10)
        elif method == "DELETE":
            resp = requests.delete(url, headers=req_headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")

        try:
            response_body = resp.json()
        except (json.JSONDecodeError, ValueError):
            response_body = resp.text

        relevant_keys = [
            "content-type", "content-length", "date", "server",
            "access-control-allow-origin", "x-response-time",
        ]
        filtered_headers = {
            k: v
            for k, v in dict(resp.headers).items()
            if k.lower() in relevant_keys
        }

        return {
            "status_code": resp.status_code,
            "headers": filtered_headers,
            "body": response_body,
        }
    except requests.ConnectionError as e:
        return {
            "status_code": 0,
            "headers": {},
            "body": {"error": f"Connection failed: {str(e)}"},
        }
    except requests.Timeout as e:
        return {
            "status_code": 0,
            "headers": {},
            "body": {"error": f"Request timed out: {str(e)}"},
        }
    except Exception as e:
        return {
            "status_code": 0,
            "headers": {},
            "body": {"error": f"Request failed: {str(e)}"},
        }


def build_snapshot(endpoint, response):
    """Build a complete snapshot dict."""
    meta = {
        "recorded_at": now_iso(),
        "method": endpoint["method"],
        "path": endpoint["path"],
        "note": endpoint["note"],
        "python": sys.executable,
    }

    request_info = {
        "method": endpoint["method"],
        "path": endpoint["path"],
        "headers": dict(endpoint["headers"]),
    }
    if endpoint["body"] is not None:
        request_info["body"] = endpoint["body"]

    return {
        "meta": meta,
        "request": request_info,
        "response": response,
    }


def save_snapshot(endpoint, response):
    """Save a snapshot to disk."""
    snapshot = build_snapshot(endpoint, response)
    filepath = SNAPSHOT_FILES[endpoint["file_slug"]]
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return filepath


def load_snapshot(endpoint):
    """Load a snapshot from disk."""
    filepath = SNAPSHOT_FILES[endpoint["file_slug"]]
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def body_matches(actual, expected, path=""):
    """
    Compare two response bodies with leniency for dynamic values.
    Returns (bool, message).
    """
    if actual is None and expected is None:
        return True, ""
    if actual is None or expected is None:
        return False, f"Type mismatch at {path}: {type(actual)} vs {type(expected)}"

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in actual:
            if key not in expected:
                continue
            ok, msg = body_matches(actual[key], expected[key], f"{path}.{key}")
            if not ok:
                return False, msg
        for key in expected:
            if key not in actual:
                return False, f"Missing key at {path}.{key}"
        return True, ""

    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) < len(expected):
            return False, f"List length mismatch at {path}: {len(actual)} < {len(expected)}"
        for i in range(min(len(actual), len(expected))):
            ok, msg = body_matches(actual[i], expected[i], f"{path}[{i}]")
            if not ok:
                return False, msg
        return True, ""

    elif isinstance(expected, str) and isinstance(actual, str):
        dynamic_fields = {
            "recorded_at", "created_at", "updated_at", "last_heartbeat",
            "connected_at", "last_accessed", "mtime", "date", "expires_at",
            "token", "session_id", "user_id", "display_name", "message",
            "detail", "agent_id", "agent_name", "status", "title",
            "task_id", "task_name", "schedule_type", "target_type",
            "source", "location", "name", "type", "version",
            "schedule_config", "error", "id",
            "audio",
        }
        field_name = path.rsplit(".", 1)[-1] if "." in path else path
        if field_name in dynamic_fields:
            return True, ""
        if actual == expected:
            return True, ""
        return False, f"String mismatch at {path}: '{actual}' vs '{expected}'"

    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return True, ""

    elif isinstance(expected, bool) and isinstance(actual, bool):
        if actual == expected:
            return True, ""
        return False, f"Bool mismatch at {path}: {actual} vs {expected}"

    else:
        if actual == expected:
            return True, ""
        return False, f"Value mismatch at {path}: {actual} vs {expected}"


def compare_responses(actual, expected):
    """Compare actual response against expected snapshot."""
    details = {}

    status_match = actual["status_code"] == expected["status_code"]
    details["status_code"] = {
        "match": status_match,
        "actual": actual["status_code"],
        "expected": expected["status_code"],
    }
    if not status_match:
        return False, details

    actual_ct = actual["headers"].get("content-type", "")
    expected_ct = expected["headers"].get("content-type", "")
    content_type_match = True
    if expected_ct:
        content_type_match = actual_ct.startswith(expected_ct.split(";")[0].strip())
    details["content_type"] = {
        "match": content_type_match,
        "actual": actual_ct,
        "expected": expected_ct,
    }

    body_ok, body_msg = body_matches(actual["body"], expected["body"])
    details["body"] = {
        "match": body_ok,
        "message": body_msg,
        "actual_summary": _summarize_body(actual["body"]),
        "expected_summary": _summarize_body(expected["body"]),
    }

    return body_ok and status_match and content_type_match, details


def _summarize_body(body, max_len=200):
    if isinstance(body, dict):
        if "error" in body:
            return f"error: {str(body['error'])[:max_len]}"
        return json.dumps(body, ensure_ascii=False)[:max_len]
    elif isinstance(body, list):
        return f"list[{len(body)} items]"
    elif isinstance(body, str):
        return body[:max_len]
    return str(body)[:max_len]


# ============================================================
# Server Management
# ============================================================

_server_process = None


def is_server_running():
    try:
        resp = requests.get(f"{CFG['base_url']}/health", timeout=2)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def kill_process_on_port(port):
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        stdout = result.stdout or ""
        for line in stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and f":{port}" in parts[1]:
                pid = parts[-1]
                if pid and pid.isdigit():
                    print(f"  Killing PID {pid} on port {port}...")
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True, timeout=5,
                    )
                    return True
    except Exception as e:
        print(f"  Warning: could not kill process on port {port}: {e}")
    return False


def start_server():
    global _server_process

    if is_server_running():
        print(f"  Server already running on {CFG['base_url']}")
        return True

    kill_process_on_port(CFG["port"])
    time.sleep(1)

    cmd = [
        str(PYTHON_PATH),
        "-m", "uvicorn",
        "main:app",
        "--port", str(CFG["port"]),
        "--host", CFG["host"],
        "--log-level", "warning",
    ]

    print(f"  Starting server: {' '.join(cmd)}")
    _server_process = subprocess.Popen(
        cmd,
        cwd=str(BACKEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for i in range(30):
        time.sleep(1)
        if is_server_running():
            print(f"  Server started (PID {_server_process.pid})")
            return True

    print("  ERROR: Server failed to start")
    return False


def stop_server():
    global _server_process
    if _server_process is not None:
        print(f"  Stopping server (PID {_server_process.pid})...")
        try:
            _server_process.terminate()
            _server_process.wait(timeout=10)
        except Exception:
            try:
                _server_process.kill()
            except Exception:
                pass
        _server_process = None
        print("  Server stopped")


# ============================================================
# Recording
# ============================================================


def record_snapshots():
    if not start_server():
        return False

    auth_token = None
    results = []
    failed = 0

    for ep in ENDPOINTS:
        slug = ep["file_slug"]
        method = ep["method"]
        path = ep["path"]
        label = f"{method} {path}"

        print(f"  [{slug}] Recording {label}...", end=" ", flush=True)

        token = auth_token if ep.get("needs_auth") else None
        response = make_request(method, path, ep["body"], ep["headers"], token)
        save_snapshot(ep, response)

        if slug == "login":
            if isinstance(response.get("body"), dict) and response["body"].get("success"):
                auth_token = response["body"].get("token")
                print(f"OK (token saved)", end="")
            else:
                print(f"OK", end="")
        else:
            if response["status_code"] == 0:
                print(f"FAIL (connection error)", end="")
                failed += 1
            else:
                print(f"OK [{response['status_code']}]", end="")

        print()
        results.append((slug, response))

    print(f"\n  Recorded {len(results) - failed}/{len(results)} snapshots")
    if failed:
        print(f"  WARNING: {failed} endpoint(s) failed to record")

    stop_server()
    return failed == 0


# ============================================================
# Verification
# ============================================================


def verify_snapshots():
    if not start_server():
        return False

    auth_token = None
    passed = 0
    failed = 0
    skipped = 0

    for ep in ENDPOINTS:
        slug = ep["file_slug"]
        method = ep["method"]
        path = ep["path"]
        label = f"{method} {path}"

        snapshot = load_snapshot(ep)
        if snapshot is None:
            print(f"  [{slug}] SKIP (no snapshot file)")
            skipped += 1
            continue

        token = auth_token if ep.get("needs_auth") else None
        print(f"  [{slug}] Verifying {label}...", end=" ", flush=True)
        response = make_request(method, path, ep["body"], ep["headers"], token)

        if slug == "login":
            if isinstance(response.get("body"), dict) and response["body"].get("success"):
                auth_token = response["body"].get("token")
                print(f"OK (token)", end="")
                passed += 1
                print()
                continue

        if response["status_code"] == 0:
            print(f"FAIL (connection error)")
            failed += 1
            continue

        expected_response = snapshot["response"]
        is_match, comp_details = compare_responses(response, expected_response)

        if is_match:
            print(f"PASS [{response['status_code']}]")
            passed += 1
        else:
            print(f"FAIL [{response['status_code']}]")
            failed += 1
            _print_mismatch(comp_details)

    print(f"\n  Results: {passed} passed, {failed} failed, {skipped} skipped")
    stop_server()
    return failed == 0


def _print_mismatch(details):
    for key, info in details.items():
        if isinstance(info, dict) and info.get("match") is False:
            if key == "status_code":
                print(f"           Status: expected {info['expected']}, got {info['actual']}")
            elif key == "body":
                print(f"           Body: {info.get('message', 'mismatch')}")
                print(f"           Actual: {info.get('actual_summary', '')[:100]}")
                print(f"           Expected: {info.get('expected_summary', '')[:100]}")
            elif key == "content_type":
                print(f"           Content-Type: expected '{info['expected']}', got '{info['actual']}'")


# ============================================================
# Main
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Record or verify API behavior snapshots for LiveLog-AI"
    )
    parser.add_argument("--record", action="store_true", help="Record new snapshots")
    parser.add_argument("--port", type=int, default=CFG["port"], help=f"Port (default: {CFG['port']})")
    args = parser.parse_args()

    if args.port != CFG["port"]:
        CFG["port"] = args.port
        _rebuild_url()

    os.chdir(str(BACKEND_DIR))

    if args.record:
        print("=== Recording API Behavior Snapshots ===\n")
        success = record_snapshots()
    else:
        print("=== Verifying API Behavior ===\n")
        success = verify_snapshots()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
