#!/usr/bin/env python3
"""
Chicken Trainer Ranking Server
Full-featured HTTP server using Python stdlib only.
Run: python3 server.py
"""

import copy
import json
import os
import uuid
import time
import csv
import io
import cgi
import gzip
import mimetypes
import random
import string
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

# === CONFIG (change these) ===
ADMIN_PASSWORD = "admin1234"
DEVICE_KEY     = "CHICKEN_SECRET_2026"
PORT           = int(os.environ.get("PORT", 8080))  # 雲端 (Render/Fly) 用 PORT env，本機預設 8080
DATA_FILE      = "data.json"
UPLOAD_DIR     = "uploads"
# =============================

START_TIME = time.time()
ADMIN_TOKENS = {}  # token -> created_at

# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------
_data_cache = None        # cached data dict
_data_cache_mtime = None  # mtime when last loaded

_html_cache = {}  # filename -> (mtime, bytes)
_static_cache = {}  # filepath -> (mtime, bytes)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_data():
    global _data_cache, _data_cache_mtime
    if not os.path.exists(DATA_FILE):
        empty = {"records": [], "images": [], "announcement": "", "devices": [], "activity": [], "settings": {}}
        _data_cache = empty
        _data_cache_mtime = None
        return empty
    mtime = os.path.getmtime(DATA_FILE)
    if _data_cache is not None and _data_cache_mtime == mtime:
        return copy.deepcopy(_data_cache)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception:
            data = {}
    data.setdefault("records", [])
    data.setdefault("images", [])
    data.setdefault("announcement", "")
    data.setdefault("devices", [])
    data.setdefault("activity", [])
    data.setdefault("settings", {})
    _data_cache = data
    _data_cache_mtime = mtime
    return copy.deepcopy(data)


def save_data(data):
    global _data_cache, _data_cache_mtime
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Update cache immediately after write
    _data_cache = copy.deepcopy(data)
    _data_cache_mtime = os.path.getmtime(DATA_FILE)


def make_id():
    return uuid.uuid4().hex[:8]


def make_rename_code():
    """Generate a 5-char uppercase+digit rename code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=5))


def make_rename_pin():
    """Generate a 4-digit PIN."""
    return str(random.randint(1000, 9999))


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def log_activity(data, action, detail=""):
    entry = {"ts": now_str(), "action": action, "detail": detail}
    data["activity"].append(entry)
    # Keep only last 500 entries to prevent unbounded growth
    if len(data["activity"]) > 500:
        data["activity"] = data["activity"][-500:]


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def is_admin(handler):
    token = handler.headers.get("X-Admin-Token", "")
    return token != "" and token in ADMIN_TOKENS


def body_has_device_key(body):
    return body.get("device_key", "") == DEVICE_KEY


def requires_auth(handler, body=None):
    """Return True if request is authorized (admin token OR device_key in body)."""
    if is_admin(handler):
        return True
    if body and body_has_device_key(body):
        return True
    return False


def find_device_by_key(data, key):
    """Find device by device_key. Returns device dict or None."""
    for dev in data.get("devices", []):
        if dev.get("key", "") == key:
            return dev
    return None


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class ChickenHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    # -----------------------------------------------------------------------
    # Low-level helpers
    # -----------------------------------------------------------------------

    def _accepts_gzip(self):
        return "gzip" in self.headers.get("Accept-Encoding", "")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if self._accepts_gzip() and len(body) > 512:
            body = gzip.compress(body, compresslevel=6)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json({"error": message}, status)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Token")

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def get_query(self):
        parsed = urlparse(self.path)
        return parse_qs(parsed.query)

    def qval(self, qs, key, default=""):
        vals = qs.get(key, [])
        return vals[0] if vals else default

    # -----------------------------------------------------------------------
    # OPTIONS (CORS preflight)
    # -----------------------------------------------------------------------

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # -----------------------------------------------------------------------
    # GET routing
    # -----------------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/api/status":
            self.handle_status()
        elif path == "/api/records/all":
            self.handle_get_records_all()
        elif path == "/api/records":
            self.handle_get_records()
        elif path == "/api/leaderboard":
            self.handle_leaderboard()
        elif path == "/api/images":
            self.handle_list_images()
        elif path == "/api/announcement":
            self.handle_get_announcement()
        elif path == "/api/backup":
            self.handle_backup()
        elif path == "/api/export/csv":
            self.handle_export_csv()
        elif path == "/api/devices":
            self.handle_get_devices()
        elif path == "/api/activity":
            self.handle_get_activity()
        elif path == "/api/updates":
            self.handle_updates()
        elif path.startswith("/uploads/"):
            self.serve_static_file(path)
        elif path.startswith("/static/"):
            rel = unquote(parsed.path[8:])  # strip /static/ and decode URL encoding
            fpath = os.path.join('static', rel)
            if os.path.isfile(fpath):
                mt, _ = mimetypes.guess_type(fpath)
                s_mtime = os.path.getmtime(fpath)
                s_etag = f'"{int(s_mtime)}-{os.path.getsize(fpath)}"'
                if self.headers.get("If-None-Match", "") == s_etag:
                    self.send_response(304)
                    self._cors_headers()
                    self.end_headers()
                    return
                # In-memory static file cache
                cached = _static_cache.get(fpath)
                if cached and cached[0] == s_mtime:
                    file_bytes = cached[1]
                else:
                    with open(fpath, 'rb') as f:
                        file_bytes = f.read()
                    _static_cache[fpath] = (s_mtime, file_bytes)
                self.send_response(200)
                self.send_header('Content-Type', mt or 'application/octet-stream')
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.send_header('ETag', s_etag)
                # Gzip for text-based static files (js, css, svg)
                if self._accepts_gzip() and mt and any(mt.startswith(t) for t in ('text/', 'application/javascript', 'application/json', 'image/svg')):
                    body = gzip.compress(file_bytes, compresslevel=6)
                    self.send_header('Content-Encoding', 'gzip')
                else:
                    body = file_bytes
                self.send_header('Content-Length', str(len(body)))
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        elif path == "/":
            self.serve_index()
        elif path == "/simulator":
            self.serve_html_file("simulator.html")
        elif path == "/rules":
            self.serve_html_file("rules.html")
        elif path == "/buy":
            self.serve_html_file("buy.html")
        elif path == "/faq":
            self.serve_html_file("faq.html")
        elif path == "/support":
            self.serve_html_file("support.html")
        elif path == "/about":
            self.serve_html_file("about.html")
        else:
            self.send_error_json(404, "Not found")

    # -----------------------------------------------------------------------
    # POST routing
    # -----------------------------------------------------------------------

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/login":
            self.handle_login()
        elif path == "/api/logout":
            self.handle_logout()
        elif path == "/api/records":
            self.handle_add_record()
        elif path == "/api/sync":
            self.handle_sync()
        elif path == "/api/rename":
            self.handle_rename()
        elif path == "/api/upload":
            self.handle_upload()
        elif path == "/api/restore":
            self.handle_restore()
        elif path == "/api/devices":
            self.handle_create_device()
        else:
            self.send_error_json(404, "Not found")

    # -----------------------------------------------------------------------
    # PUT routing
    # -----------------------------------------------------------------------

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/announcement":
            self.handle_put_announcement()
        elif path.startswith("/api/records/"):
            record_id = path[len("/api/records/"):]
            self.handle_edit_record(record_id)
        elif path.startswith("/api/devices/"):
            device_id = path[len("/api/devices/"):]
            self.handle_edit_device(device_id)
        else:
            self.send_error_json(404, "Not found")

    # -----------------------------------------------------------------------
    # DELETE routing
    # -----------------------------------------------------------------------

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path.startswith("/api/records/"):
            record_id = path[len("/api/records/"):]
            self.handle_delete_record(record_id)
        elif path.startswith("/api/images/"):
            image_id = path[len("/api/images/"):]
            self.handle_delete_image(image_id)
        elif path.startswith("/api/devices/"):
            device_id = path[len("/api/devices/"):]
            self.handle_delete_device(device_id)
        else:
            self.send_error_json(404, "Not found")

    # -----------------------------------------------------------------------
    # Static file serving
    # -----------------------------------------------------------------------

    def serve_html_file(self, filename):
        if os.path.exists(filename):
            mtime = os.path.getmtime(filename)
            size = os.path.getsize(filename)
            etag = f'"{int(mtime)}-{size}"'
            client_etag = self.headers.get("If-None-Match", "")
            if client_etag == etag:
                self.send_response(304)
                self._cors_headers()
                self.end_headers()
                return
            # In-memory HTML cache keyed by (filename, mtime)
            cached = _html_cache.get(filename)
            if cached and cached[0] == mtime:
                content = cached[1]
            else:
                with open(filename, "rb") as f:
                    content = f.read()
                _html_cache[filename] = (mtime, content)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=300")
            self.send_header("ETag", etag)
            if self._accepts_gzip() and len(content) > 1024:
                body = gzip.compress(content, compresslevel=6)
                self.send_header("Content-Encoding", "gzip")
            else:
                body = content
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def serve_index(self):
        self.serve_html_file("index.html")

    def serve_static_file(self, path):
        safe_path = os.path.normpath("." + path)
        # Prevent directory traversal
        if not safe_path.startswith(os.path.normpath(UPLOAD_DIR)):
            self.send_error_json(403, "Forbidden")
            return
        if os.path.exists(safe_path) and os.path.isfile(safe_path):
            mime, _ = mimetypes.guess_type(safe_path)
            mime = mime or "application/octet-stream"
            mtime = os.path.getmtime(safe_path)
            etag = f'"{int(mtime)}-{os.path.getsize(safe_path)}"'
            client_etag = self.headers.get("If-None-Match", "")
            if client_etag == etag:
                self.send_response(304)
                self._cors_headers()
                self.end_headers()
                return
            with open(safe_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            # Images and assets: cache 1 day; HTML served separately
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("ETag", etag)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error_json(404, "File not found")

    # -----------------------------------------------------------------------
    # Auth handlers
    # -----------------------------------------------------------------------

    def handle_login(self):
        body = self.read_json_body()
        if body.get("password", "") == ADMIN_PASSWORD:
            token = str(uuid.uuid4())
            ADMIN_TOKENS[token] = time.time()
            data = load_data()
            log_activity(data, "login", "Admin logged in")
            save_data(data)
            self.send_json({"token": token})
        else:
            self.send_error_json(401, "Invalid password")

    def handle_logout(self):
        token = self.headers.get("X-Admin-Token", "")
        if token in ADMIN_TOKENS:
            del ADMIN_TOKENS[token]
            data = load_data()
            log_activity(data, "logout", "Admin logged out")
            save_data(data)
        self.send_json({"ok": True})

    # -----------------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------------

    def handle_status(self):
        data = load_data()
        self.send_json({
            "ok": True,
            "records": len(data["records"]),
            "uptime_s": int(time.time() - START_TIME)
        })

    # -----------------------------------------------------------------------
    # Records
    # -----------------------------------------------------------------------

    def _filter_sort_records(self, records, qs, include_hidden=False):
        if not include_hidden:
            records = [r for r in records if not r.get("hidden", False)]

        # Source filter: exclude simulator from physical rankings and vice versa
        source_filter = self.qval(qs, "source")
        if source_filter == "physical":
            records = [r for r in records if r.get("source", "physical") == "physical" and r.get("device_id", "") != "simulator"]
        elif source_filter == "simulator":
            records = [r for r in records if r.get("source") == "simulator" or r.get("device_id") == "simulator"]

        diff = self.qval(qs, "difficulty").upper()
        if diff in ("EASY", "NORMAL", "HARD"):
            records = [r for r in records if r.get("difficulty", "").upper() == diff]

        search = self.qval(qs, "search")
        if search:
            sl = search.lower()
            records = [r for r in records if sl in r.get("name", "").lower()]

        from_date = self.qval(qs, "from")
        if from_date:
            records = [r for r in records if r.get("date", "") >= from_date]

        to_date = self.qval(qs, "to")
        if to_date:
            records = [r for r in records if r.get("date", "")[:10] <= to_date]

        DIFF_WEIGHT = {"EASY": 1.0, "NORMAL": 1.2, "HARD": 1.5}

        sort_field = self.qval(qs, "sort", "composite")
        order = self.qval(qs, "order", "desc")
        reverse = (order != "asc")

        def sort_key(r):
            if sort_field == "date":
                return r.get("date", "")
            elif sort_field == "survival":
                return r.get("survival", 0)
            elif sort_field == "composite":
                w = DIFF_WEIGHT.get(r.get("difficulty", "EASY").upper(), 1.0)
                return r.get("score", 0) * w
            else:
                return r.get("score", 0)

        records = sorted(records, key=sort_key, reverse=reverse)
        return records

    def handle_get_records(self):
        qs = self.get_query()
        data = load_data()
        # Public: only approved records
        records = [r for r in data["records"] if r.get("approved", True)]
        records = self._filter_sort_records(records, qs, include_hidden=False)

        try:
            page = max(1, int(self.qval(qs, "page", "1")))
        except ValueError:
            page = 1
        try:
            per_page = max(1, int(self.qval(qs, "per_page", "20")))
        except ValueError:
            per_page = 20

        total = len(records)
        start = (page - 1) * per_page
        end = start + per_page
        self.send_json({
            "records": records[start:end],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page)
        })

    def handle_get_records_all(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        qs = self.get_query()
        data = load_data()
        records = self._filter_sort_records(data["records"], qs, include_hidden=True)
        self.send_json({"records": records, "total": len(records)})

    def handle_add_record(self):
        body = self.read_json_body()
        if not requires_auth(self, body):
            self.send_error_json(401, "Unauthorized")
            return

        name = body.get("name", "").strip()
        if not name:
            self.send_error_json(400, "name is required")
            return

        diff = body.get("difficulty", "NORMAL").upper()
        if diff not in ("EASY", "NORMAL", "HARD"):
            diff = "NORMAL"

        record = {
            "id": make_id(),
            "name": name,
            "score": max(0, min(100, int(body.get("score", 0)))),
            "survival": max(0, min(100, int(body.get("survival", 0)))),
            "duration": max(0, int(body.get("duration", 0))),
            "difficulty": diff,
            "date": now_str(),
            "note": str(body.get("note", "")),
            "hidden": False,
            "verified": False,
            "device_id": "manual",
            "approved": True
        }

        data = load_data()
        data["records"].append(record)
        log_activity(data, "add_record", f"Player: {name}, Score: {record['score']}")
        save_data(data)
        self.send_json({"ok": True, "record": record}, 201)

    def handle_edit_record(self, record_id):
        body = self.read_json_body()
        if not requires_auth(self, body):
            self.send_error_json(401, "Unauthorized")
            return

        data = load_data()
        record = next((r for r in data["records"] if r["id"] == record_id), None)
        if not record:
            self.send_error_json(404, "Record not found")
            return

        action = "edit_record"
        for field in ("name", "score", "survival", "duration", "difficulty", "note", "hidden", "verified", "approved"):
            if field not in body:
                continue
            val = body[field]
            if field == "difficulty":
                val = str(val).upper()
                if val not in ("EASY", "NORMAL", "HARD"):
                    continue
            elif field in ("score", "survival", "duration"):
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    continue
            elif field in ("hidden", "verified", "approved"):
                val = bool(val)
            if field == "hidden":
                action = "hide_record"
            record[field] = val

        log_activity(data, action, f"Record ID: {record_id}, Player: {record.get('name','')}")
        save_data(data)
        self.send_json({"ok": True, "record": record})

    def handle_delete_record(self, record_id):
        body = self.read_json_body()
        if not requires_auth(self, body):
            self.send_error_json(401, "Unauthorized")
            return

        data = load_data()
        rec = next((r for r in data["records"] if r["id"] == record_id), None)
        before = len(data["records"])
        data["records"] = [r for r in data["records"] if r["id"] != record_id]
        if len(data["records"]) == before:
            self.send_error_json(404, "Record not found")
            return
        player_name = rec.get("name", "") if rec else record_id
        log_activity(data, "delete_record", f"Record ID: {record_id}, Player: {player_name}")
        save_data(data)
        self.send_json({"ok": True})

    # -----------------------------------------------------------------------
    # Leaderboard
    # -----------------------------------------------------------------------

    def handle_leaderboard(self):
        qs = self.get_query()
        try:
            limit = min(100, max(1, int(self.qval(qs, "limit", "10"))))
        except ValueError:
            limit = 10

        data = load_data()
        visible = [r for r in data["records"] if not r.get("hidden", False) and r.get("approved", True)]
        sorted_records = sorted(visible, key=lambda r: r.get("score", 0), reverse=True)

        result = []
        for i, r in enumerate(sorted_records[:limit]):
            result.append({
                "rank": i + 1,
                "name": r["name"],
                "score": r["score"],
                "difficulty": r["difficulty"]
            })
        self.send_json(result)

    # -----------------------------------------------------------------------
    # Sync (D1 Mini)
    # -----------------------------------------------------------------------

    def handle_sync(self):
        body = self.read_json_body()
        if not body_has_device_key(body):
            self.send_error_json(401, "Invalid device_key")
            return

        name = str(body.get("name", "Device")).strip() or "Device"
        diff = str(body.get("difficulty", "NORMAL")).upper()
        if diff not in ("EASY", "NORMAL", "HARD"):
            diff = "NORMAL"

        device_id = str(body.get("device_id", "unknown")).strip() or "unknown"

        data = load_data()

        # 自動核准所有上傳（device_key 對就放行，不再卡審核）
        device_key = body.get("device_key", "")
        registered_device = find_device_by_key(data, device_key)
        is_simulator = (device_id == "simulator" or body.get("source") == "simulator")
        approved = True  # ← 改成全部自動核准

        rename_code = make_rename_code()
        rename_pin  = make_rename_pin()

        record = {
            "id": make_id(),
            "name": name,
            "score": max(0, min(100, int(body.get("score", 0)))),
            "survival": max(0, min(100, int(body.get("survival", 0)))),
            "duration": max(0, int(body.get("duration", 0))),
            "difficulty": diff,
            "date": now_str(),
            "note": "via D1 Mini",
            "hidden": False,
            "verified": True,
            "device_id": device_id,
            "source": "simulator" if is_simulator else "physical",
            "approved": approved,
            "rename_code": rename_code,
            "rename_pin":  rename_pin,
        }

        data["records"].append(record)
        log_activity(data, "sync", f"Device: {device_id}, Player: {name}, Score: {record['score']}")
        save_data(data)

        visible = [r for r in data["records"] if not r.get("hidden", False) and r.get("approved", True)]
        sorted_records = sorted(visible, key=lambda r: r.get("score", 0), reverse=True)
        rank = next((i + 1 for i, r in enumerate(sorted_records) if r["id"] == record["id"]), 0)

        self.send_json({"ok": True, "rank": rank, "record": record, "approved": approved,
                        "rename_code": rename_code, "rename_pin": rename_pin})

    def handle_rename(self):
        """Allow renaming a record using a rename_code + rename_pin."""
        body = self.read_json_body()
        code     = str(body.get("code", "")).upper().strip()
        pin      = str(body.get("pin", "")).strip()
        new_name = str(body.get("new_name", "")).strip()

        if not code or not pin or not new_name:
            self.send_error_json(400, "Missing fields: code, pin, new_name")
            return
        if len(new_name) > 24:
            self.send_error_json(400, "Name too long (max 24 chars)")
            return

        data = load_data()
        record = next(
            (r for r in data["records"]
             if r.get("rename_code") == code and r.get("rename_pin") == pin),
            None
        )

        if not record:
            self.send_error_json(404, "Invalid code or PIN")
            return

        old_name = record.get("name", "")
        record["name"] = new_name
        log_activity(data, "rename", f"Record ID: {record['id']}, {old_name} → {new_name}")
        save_data(data)
        self.send_json({"ok": True, "name": new_name, "score": record.get("score"), "date": record.get("date")})

    # -----------------------------------------------------------------------
    # Devices
    # -----------------------------------------------------------------------

    def handle_get_devices(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        data = load_data()
        self.send_json({"devices": data.get("devices", [])})

    def handle_create_device(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        body = self.read_json_body()
        name = str(body.get("name", "")).strip()
        if not name:
            self.send_error_json(400, "name is required")
            return
        key = str(body.get("key", "")).strip() or f"KEY_{uuid.uuid4().hex[:12].upper()}"
        device = {
            "id": f"dev{make_id()}",
            "name": name,
            "key": key,
            "created": datetime.now().strftime("%Y-%m-%d")
        }
        data = load_data()
        data["devices"].append(device)
        log_activity(data, "create_device", f"Device: {name} ({device['id']})")
        save_data(data)
        self.send_json({"ok": True, "device": device}, 201)

    def handle_edit_device(self, device_id):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        body = self.read_json_body()
        data = load_data()
        device = next((d for d in data["devices"] if d["id"] == device_id), None)
        if not device:
            self.send_error_json(404, "Device not found")
            return
        if "name" in body:
            device["name"] = str(body["name"]).strip()
        if "key" in body:
            device["key"] = str(body["key"]).strip()
        save_data(data)
        self.send_json({"ok": True, "device": device})

    def handle_delete_device(self, device_id):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        data = load_data()
        before = len(data["devices"])
        data["devices"] = [d for d in data["devices"] if d["id"] != device_id]
        if len(data["devices"]) == before:
            self.send_error_json(404, "Device not found")
            return
        log_activity(data, "delete_device", f"Device ID: {device_id}")
        save_data(data)
        self.send_json({"ok": True})

    # -----------------------------------------------------------------------
    # Activity log
    # -----------------------------------------------------------------------

    def handle_updates(self):
        data = load_data()
        records = data.get('records', [])
        approved = [r for r in records if r.get('approved', True) and not r.get('hidden', False)]
        last_date = max((r.get('date', '') for r in approved), default='')
        self.send_json({
            'count': len(approved),
            'last_date': last_date
        })

    def handle_get_activity(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        data = load_data()
        activity = data.get("activity", [])
        # Return last 100, newest first
        recent = list(reversed(activity[-100:]))
        self.send_json({"activity": recent})

    # -----------------------------------------------------------------------
    # Images
    # -----------------------------------------------------------------------

    def handle_list_images(self):
        data = load_data()
        self.send_json({"images": data["images"]})

    def handle_upload(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self.send_error_json(400, "Expected multipart/form-data")
            return

        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
            "CONTENT_LENGTH": self.headers.get("Content-Length", "0")
        }
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ)

        if "file" not in form:
            self.send_error_json(400, "No file field in form")
            return

        file_item = form["file"]
        filename = file_item.filename or "upload.bin"
        safe_name = os.path.basename(filename)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            self.send_error_json(400, "Invalid file type (jpg/png/gif/webp only)")
            return

        image_id = make_id()
        stored_name = f"{image_id}{ext}"
        stored_path = os.path.join(UPLOAD_DIR, stored_name)

        with open(stored_path, "wb") as f:
            f.write(file_item.file.read())

        image_record = {
            "id": image_id,
            "filename": stored_name,
            "original_name": safe_name,
            "url": f"/uploads/{stored_name}",
            "date": now_str()
        }

        data = load_data()
        data["images"].append(image_record)
        log_activity(data, "upload_image", f"File: {safe_name}")
        save_data(data)
        self.send_json({"ok": True, "image": image_record}, 201)

    def handle_delete_image(self, image_id):
        body = self.read_json_body()
        if not requires_auth(self, body):
            self.send_error_json(401, "Unauthorized")
            return

        data = load_data()
        image = next((img for img in data["images"] if img["id"] == image_id), None)
        if not image:
            self.send_error_json(404, "Image not found")
            return

        file_path = os.path.join(UPLOAD_DIR, image["filename"])
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

        data["images"] = [img for img in data["images"] if img["id"] != image_id]
        log_activity(data, "delete_image", f"File: {image.get('original_name', image_id)}")
        save_data(data)
        self.send_json({"ok": True})

    # -----------------------------------------------------------------------
    # Announcement
    # -----------------------------------------------------------------------

    def handle_get_announcement(self):
        data = load_data()
        self.send_json({"text": data.get("announcement", "")})

    def handle_put_announcement(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        body = self.read_json_body()
        data = load_data()
        data["announcement"] = str(body.get("text", ""))
        log_activity(data, "put_announcement", f"Length: {len(data['announcement'])} chars")
        save_data(data)
        self.send_json({"ok": True})

    # -----------------------------------------------------------------------
    # Backup / Restore / Export CSV
    # -----------------------------------------------------------------------

    def handle_backup(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        data = load_data()
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        filename = f"chicken_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_restore(self):
        if not is_admin(self):
            self.send_error_json(401, "Admin token required")
            return
        body = self.read_json_body()
        if "records" not in body:
            self.send_error_json(400, "Invalid backup format: missing 'records'")
            return
        restored = {
            "records": body.get("records", []),
            "images": body.get("images", []),
            "announcement": body.get("announcement", ""),
            "devices": body.get("devices", []),
            "activity": body.get("activity", []),
            "settings": body.get("settings", {})
        }
        log_activity(restored, "restore", f"Restored {len(restored['records'])} records")
        save_data(restored)
        self.send_json({"ok": True, "records": len(restored["records"])})

    def handle_export_csv(self):
        data = load_data()
        visible = [r for r in data["records"] if not r.get("hidden", False)]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "score", "survival", "duration", "difficulty", "date", "note", "verified", "device_id", "approved"])
        for r in visible:
            writer.writerow([
                r.get("id", ""),
                r.get("name", ""),
                r.get("score", 0),
                r.get("survival", 0),
                r.get("duration", 0),
                r.get("difficulty", ""),
                r.get("date", ""),
                r.get("note", ""),
                r.get("verified", False),
                r.get("device_id", ""),
                r.get("approved", True)
            ])

        # UTF-8 BOM for Excel compatibility
        csv_bytes = "\ufeff".encode("utf-8") + output.getvalue().encode("utf-8")
        filename = f"chicken_records_{datetime.now().strftime('%Y%m%d')}.csv"
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(csv_bytes)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(csv_bytes)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        save_data({"records": [], "images": [], "announcement": "", "devices": [], "activity": [], "settings": {}})

    server = HTTPServer(("0.0.0.0", PORT), ChickenHandler)
    print(f"Chicken Trainer Ranking Server running at http://0.0.0.0:{PORT}")
    print(f"  Data file : {DATA_FILE}")
    print(f"  Upload dir: {UPLOAD_DIR}")
    print(f"  Admin pw  : {ADMIN_PASSWORD}")
    print(f"  Device key: {DEVICE_KEY}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run()
