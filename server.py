"""
個資確認系統 — Personal Info Confirmation
HTTP server (Python stdlib only) for the registration office.

Roles:
  - student:    確認自己的個資
  - officer:    看全班「確認狀態」(無個資內容) + 自己的個資
  - registrar:  看全班完整個資、可直接修正
"""
import json
import os
import secrets
import threading
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

# ── Paths / config ────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
STATIC_DIR = os.path.join(ROOT, "static")
PORT = int(os.environ.get("PORT", 8765))
TPE = timezone(timedelta(hours=8))

# ── Data load / save (with simple file lock) ──────────────────
_LOCK = threading.Lock()


def _load(name, default):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return default
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(name, obj):
    p = os.path.join(DATA_DIR, name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def load_users():
    return _load("users.json", [])


def load_students():
    return _load("students.json", [])


def load_classroom():
    return _load("classroom.json", {})


# ── Sessions (in-memory) ──────────────────────────────────────
SESSIONS = {}  # token -> {"username": str, "created": iso}


def now_iso():
    return datetime.now(TPE).strftime("%Y-%m-%d %H:%M:%S")


def hash_pw(p):
    return sha256(p.encode("utf-8")).hexdigest()


def find_user(username):
    for u in load_users():
        if u["username"] == username:
            return u
    return None


def auth_user(token):
    """Return user dict or None"""
    if not token or token not in SESSIONS:
        return None
    return find_user(SESSIONS[token]["username"])


# ── Public student view (officer sees only this) ──────────────
def public_view(s):
    """學藝股長能看到的欄位 — 只有姓名、座號、確認狀態"""
    return {
        "seat": s["seat"],
        "name": s["name"],
        "confirmed": s["confirmed"],
        "confirmed_at": s["confirmed_at"],
    }


# ── HTTP handler ──────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "InfoConfirm/1.0"

    # ── helpers ────────────────────────────────────────────
    def log_message(self, fmt, *args):
        # 輕量化日誌
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.command} {self.path}")

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8", extra_headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, obj, code=200, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8", extra_headers)

    def _send_file(self, fpath, ctype):
        if not os.path.isfile(fpath):
            self._send(404, b"Not Found")
            return
        with open(fpath, "rb") as f:
            data = f.read()
        self._send(200, data, ctype)

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _get_token(self):
        c = self.headers.get("Cookie", "")
        for part in c.split(";"):
            kv = part.strip().split("=", 1)
            if len(kv) == 2 and kv[0] == "session":
                return kv[1]
        return None

    def _require_auth(self, *allowed_roles):
        """回傳 user dict，若失敗自己回 401 並 return None"""
        u = auth_user(self._get_token())
        if u is None:
            self._send_json({"ok": False, "error": "未登入"}, 401)
            return None
        if allowed_roles and u["role"] not in allowed_roles:
            self._send_json({"ok": False, "error": "權限不足"}, 403)
            return None
        return u

    # ── routing ────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path

        # 靜態資源
        if path == "/" or path == "/index.html":
            self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._send_file(os.path.join(STATIC_DIR, "styles.css"), "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send_file(os.path.join(STATIC_DIR, "app.js"), "application/javascript; charset=utf-8")
            return

        # API
        if path == "/api/me":
            return self.api_me()
        if path == "/api/student/me":
            return self.api_student_me()
        if path == "/api/class/status":
            return self.api_class_status()
        if path == "/api/students/all":
            return self.api_students_all()
        if path == "/api/classroom":
            return self.api_classroom()
        if path == "/api/health":
            return self._send_json({"ok": True, "time": now_iso()})

        self._send(404, b"Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            return self.api_login()
        if path == "/api/logout":
            return self.api_logout()
        if path == "/api/student/confirm":
            return self.api_student_confirm()
        if path == "/api/student/note":
            return self.api_student_note()
        if path == "/api/registrar/edit":
            return self.api_registrar_edit()
        if path == "/api/registrar/reset_confirm":
            return self.api_registrar_reset_confirm()

        self._send(404, b"Not Found")

    # ── Auth ───────────────────────────────────────────────
    def api_login(self):
        body = self._read_json()
        username = (body.get("username") or "").strip()
        password = body.get("password") or ""
        u = find_user(username)
        if not u or u["password_hash"] != hash_pw(password):
            return self._send_json({"ok": False, "error": "帳號或密碼錯誤"}, 401)
        token = secrets.token_urlsafe(24)
        with _LOCK:
            SESSIONS[token] = {"username": username, "created": now_iso()}
        # HttpOnly cookie，路徑 /，預設不過期 (browser-session)
        cookie = f"session={token}; Path=/; HttpOnly; SameSite=Lax"
        self._send_json({
            "ok": True,
            "user": {"username": u["username"], "role": u["role"], "display_name": u["display_name"]}
        }, extra_headers={"Set-Cookie": cookie})

    def api_logout(self):
        token = self._get_token()
        if token and token in SESSIONS:
            with _LOCK:
                del SESSIONS[token]
        self._send_json({"ok": True}, extra_headers={
            "Set-Cookie": "session=; Path=/; Max-Age=0"
        })

    def api_me(self):
        u = auth_user(self._get_token())
        if u is None:
            return self._send_json({"ok": False}, 401)
        return self._send_json({
            "ok": True,
            "user": {
                "username": u["username"],
                "role": u["role"],
                "display_name": u["display_name"],
                "linked_seat": u.get("linked_seat"),
            }
        })

    # ── Classroom info ─────────────────────────────────────
    def api_classroom(self):
        if self._require_auth("student", "officer", "registrar") is None:
            return
        return self._send_json({"ok": True, "classroom": load_classroom()})

    # ── Student endpoints ──────────────────────────────────
    def api_student_me(self):
        """取得自己的個資 (學生 / 學藝股長 都能用，註冊組長無 linked_seat 不適用)"""
        u = self._require_auth("student", "officer")
        if u is None:
            return
        seat = u.get("linked_seat")
        if seat is None:
            return self._send_json({"ok": False, "error": "無對應學生資料"}, 400)
        for s in load_students():
            if s["seat"] == seat:
                return self._send_json({"ok": True, "student": s})
        return self._send_json({"ok": False, "error": "找不到資料"}, 404)

    def api_student_confirm(self):
        """學生確認個資正確"""
        u = self._require_auth("student", "officer")
        if u is None:
            return
        seat = u.get("linked_seat")
        if seat is None:
            return self._send_json({"ok": False, "error": "無對應學生資料"}, 400)

        with _LOCK:
            students = load_students()
            for s in students:
                if s["seat"] == seat:
                    s["confirmed"] = True
                    s["confirmed_at"] = now_iso()
                    _save("students.json", students)
                    return self._send_json({"ok": True, "confirmed_at": s["confirmed_at"]})
        return self._send_json({"ok": False, "error": "找不到資料"}, 404)

    def api_student_note(self):
        """學生留言 (例：個資哪裡有錯)"""
        u = self._require_auth("student", "officer")
        if u is None:
            return
        body = self._read_json()
        note = (body.get("note") or "").strip()[:500]
        seat = u.get("linked_seat")

        with _LOCK:
            students = load_students()
            for s in students:
                if s["seat"] == seat:
                    s["note"] = note
                    _save("students.json", students)
                    return self._send_json({"ok": True})
        return self._send_json({"ok": False, "error": "找不到資料"}, 404)

    # ── Officer endpoint ───────────────────────────────────
    def api_class_status(self):
        """全班確認狀態 (officer / registrar 都能看)"""
        u = self._require_auth("officer", "registrar")
        if u is None:
            return
        students = load_students()
        return self._send_json({
            "ok": True,
            "students": [public_view(s) for s in sorted(students, key=lambda x: x["seat"])],
            "summary": {
                "total": len(students),
                "confirmed": sum(1 for s in students if s["confirmed"]),
                "pending": sum(1 for s in students if not s["confirmed"]),
            }
        })

    # ── Registrar endpoints ────────────────────────────────
    def api_students_all(self):
        """完整個資 (registrar only)"""
        if self._require_auth("registrar") is None:
            return
        students = load_students()
        return self._send_json({"ok": True, "students": sorted(students, key=lambda x: x["seat"])})

    def api_registrar_edit(self):
        """註冊組長修正某筆學生資料"""
        if self._require_auth("registrar") is None:
            return
        body = self._read_json()
        seat = body.get("seat")
        patch = body.get("patch") or {}

        ALLOWED = {
            "name", "gender", "national_id", "dob", "blood", "religion",
            "address_household", "address_mailing",
            "phone", "father_name", "father_phone", "father_job",
            "mother_name", "mother_phone", "mother_job",
            "emergency_name", "emergency_phone", "emergency_relation",
            "home_phone",
        }
        with _LOCK:
            students = load_students()
            for s in students:
                if s["seat"] == seat:
                    for k, v in patch.items():
                        if k in ALLOWED:
                            s[k] = v
                    _save("students.json", students)
                    return self._send_json({"ok": True, "student": s})
        return self._send_json({"ok": False, "error": "找不到資料"}, 404)

    def api_registrar_reset_confirm(self):
        """註冊組長重置某人的確認狀態 (例：他確認錯了)"""
        if self._require_auth("registrar") is None:
            return
        body = self._read_json()
        seat = body.get("seat")
        with _LOCK:
            students = load_students()
            for s in students:
                if s["seat"] == seat:
                    s["confirmed"] = False
                    s["confirmed_at"] = None
                    _save("students.json", students)
                    return self._send_json({"ok": True})
        return self._send_json({"ok": False, "error": "找不到資料"}, 404)


# ── Run ───────────────────────────────────────────────────────
def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"=== 個資確認系統 ===")
    print(f"監聽 0.0.0.0:{PORT}")
    print(f"本機網址：http://localhost:{PORT}")
    print(f"")
    print(f"測試帳號：")
    print(f"  學生 test01 ~ test30   (密碼=帳號)")
    print(f"  學藝股長 officer01    (密碼: officer01)")
    print(f"  註冊組長 registrar01  (密碼: registrar01)")
    print(f"")
    print(f"按 Ctrl+C 結束")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止中…")
        server.shutdown()


if __name__ == "__main__":
    main()
