# -*- coding: utf-8 -*-

import os
import secrets
import time
import json
import hashlib
from functools import wraps
import urllib.request
import urllib.error

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    send_file,
    send_from_directory,
    session,
    abort,
)

from secrets_store import SecretsStore

app = Flask(__name__, template_folder="templates", static_folder="static")
store = SecretsStore()

# Basis-Konfiguration
BASE_URL = os.getenv("BASE_URL", "http://localhost:7143")
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
ADMIN_TIMEOUT = int(os.getenv("ADMIN_TIMEOUT", "300"))  # Sekunden
ADMIN_CONFIG_FILE = os.path.join(DATA_DIR, "admin.json")
FIXED_ADMIN_USER = "admin"

# ---------------------------------------------------------
# Version: fest im Code + optional aus /app/version.txt
# ---------------------------------------------------------
VERSION = "1.0.0"  # HIER deine Release-Version eintragen
VERSION_FILE = "/app/version.txt"

if os.path.exists(VERSION_FILE):
    try:
        with open(VERSION_FILE, "r") as vf:
            v = vf.read().strip()
            if v:
                VERSION = v
    except Exception:
        pass

# Sicherheits-Limits
MAX_TTL = 14 * 24 * 3600         # max. 14 Tage
MAX_SECRET_LEN = 4096            # max. 4k Zeichen fuer Passwort
MAX_CONTENT_LENGTH_MB = 2        # fuer Uploads (Logo)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_MB * 1024 * 1024

# MASTER_KEY aus Environment holen -> Pflicht
MASTER_KEY = os.getenv("MASTER_KEY")
if not MASTER_KEY:
    raise RuntimeError("MASTER_KEY ist nicht gesetzt! Bitte in docker-compose.yml oder Umgebung konfigurieren.")


def _derive_app_secret(master):
    """
    APP_SECRET aus MASTER_KEY ableiten.
    Anderer Kontext als fuer Fernet in secrets_store (dort: "crypt").
    """
    if isinstance(master, str):
        master = master.encode("utf-8")
    digest = hashlib.sha256(master + b"app").hexdigest()
    return digest


APP_SECRET = _derive_app_secret(MASTER_KEY)
app.secret_key = APP_SECRET

os.makedirs(DATA_DIR, exist_ok=True)

# Cookie-Sicherheit (abh. von http/https)
SECURE_COOKIES = BASE_URL.lower().startswith("https://")
app.config.update(
    SESSION_COOKIE_SECURE=SECURE_COOKIES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def _load_admin_config():
    if not os.path.exists(ADMIN_CONFIG_FILE):
        return {}
    try:
        with open(ADMIN_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_admin_config(cfg):
    with open(ADMIN_CONFIG_FILE, "w") as f:
        json.dump(cfg, f)


def _hash_password(password):
    """
    Admin-Passwort-Hash mit APP_SECRET als "pepper".
    """
    if isinstance(password, str):
        password = password.encode("utf-8")
    salt = APP_SECRET.encode("utf-8")
    return hashlib.sha256(salt + password).hexdigest()


def is_admin_password_set():
    cfg = _load_admin_config()
    return bool(cfg.get("password_hash"))


def verify_admin_password(password):
    cfg = _load_admin_config()
    stored = cfg.get("password_hash")
    if not stored:
        return False
    return stored == _hash_password(password)


def set_admin_credentials(username, password):
    """
    Admin-Benutzername und Passwort setzen.
    """
    cfg = _load_admin_config()
    cfg["username"] = (username or "").strip() or FIXED_ADMIN_USER
    cfg["password_hash"] = _hash_password(password)
    _save_admin_config(cfg)


def set_admin_password(password):
    """
    Nur das Passwort aendern, Benutzername beibehalten.
    Falls noch keiner gesetzt ist, wird auf FIXED_ADMIN_USER zurueckgegriffen.
    """
    cfg = _load_admin_config()
    username = cfg.get("username") or FIXED_ADMIN_USER
    cfg["username"] = username
    cfg["password_hash"] = _hash_password(password)
    _save_admin_config(cfg)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_root"))
        return fn(*args, **kwargs)
    return wrapper

# --------------------------------------------------------------------
# GitHub Version Check (mit einfachem Cache)
# --------------------------------------------------------------------

_latest_version_cache = {
    "value": None,
    "ts": 0.0,
}


def _parse_version(v):
    """
    "1.0.3", "v1.0.3", "1.0.3-beta" -> [1,0,3]
    Alles nicht numerische ausser '.' wird entfernt.
    """
    if not v:
        return [0]
    v = v.strip()
    cleaned = "".join(ch for ch in v if (ch.isdigit() or ch == "."))
    if not cleaned:
        return [0]
    parts = []
    for part in cleaned.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts

# Docker Hub Repo fuer Update-Check
DOCKER_REPO = os.getenv("DOCKER_REPO", "nick1122/simpleots")


def get_latest_docker_hub_version():
    """
    Holt die neueste Version von Docker Hub (Tags) und cached sie fuer 1 Stunde.
    Gibt z.B. "1.0.1" zurueck.
    """
    now = time.time()
    if _latest_version_cache["value"] is not None and (now - _latest_version_cache["ts"] < 3600):
        return _latest_version_cache["value"]

    # Docker Hub API v2
    # https://hub.docker.com/v2/repositories/nick1122/simpleots/tags?page_size=25
    api_url = f"https://hub.docker.com/v2/repositories/{DOCKER_REPO}/tags?page_size=25"
    
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "simpleots-version-check",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        # Tags parsen
        results = data.get("results", [])
        best_ver = None
        best_parts = [0, 0, 0]

        for item in results:
            tag_name = item.get("name")
            if not tag_name or tag_name == "latest":
                continue
            
            # Pruefen ob es wie eine Version aussieht (x.y.z)
            # Wir nutzen unsere _parse_version Hilfsfunktion
            parts = _parse_version(tag_name)
            
            # Vergleich
            if parts > best_parts:
                best_parts = parts
                best_ver = tag_name
        
        if best_ver:
            _latest_version_cache["value"] = best_ver
            _latest_version_cache["ts"] = now
            return best_ver
            
        return None

    except Exception:
        return None


@app.before_request
def global_guard_and_timeout():
    """
    1) Solange kein Admin-Passwort gesetzt ist:
       -> Alles (auch "/") auf /admin/ (Setup) umleiten,
          ausser /admin/*, /static/*, /logo, /favicon*.
    2) Wenn Passwort gesetzt ist:
       -> Admin-Timeout pruefen.
    """
    if not is_admin_password_set():
        path = request.path or "/"
        if (
            path.startswith("/admin")
            or path.startswith("/static")
            or path == "/logo"
            or path.startswith("/favicon")
        ):
            return
        return redirect(url_for("admin_root"))

    if not session.get("admin"):
        return

    now = time.time()
    last = session.get("last_activity")

    if last is not None and now - last > ADMIN_TIMEOUT:
        session.pop("admin", None)
        session.pop("last_activity", None)
        return redirect(url_for("admin_root"))

    session["last_activity"] = now


@app.before_request
def ensure_csrf_token():
    """
    CSRF-Token fuer Admin-Formulare in der Session halten.
    Templates greifen via {{ session.csrf_token }} darauf zu.
    """
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


def _check_csrf():
    """
    Minimaler CSRF-Schutz fuer Admin-POSTs.
    """
    if request.method != "POST":
        return
    if not request.path.startswith("/admin"):
        return

    token_form = request.form.get("csrf_token", "")
    token_session = session.get("csrf_token")
    if not token_form or not token_session or token_form != token_session:
        abort(403)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", error="")

    secret_text = (request.form.get("secret") or "").strip()
    ttl_raw = request.form.get("ttl") or ""

    if not secret_text:
        return render_template(
            "index.html",
            error="Bitte ein Passwort eingeben."
        )

    if len(secret_text) > MAX_SECRET_LEN:
        return render_template(
            "index.html",
            error="Passwort ist zu lang."
        )

    try:
        ttl = int(ttl_raw)
    except ValueError:
        return render_template(
            "index.html",
            error="Bitte eine gueltige Gueltigkeit auswaehlen."
        )

    if ttl <= 0 or ttl > MAX_TTL:
        return render_template(
            "index.html",
            error="Unzulaessige Gueltigkeit gewaehlt."
        )

    token = secrets.token_urlsafe(32)
    store.save(token, secret_text, ttl)

    link = f"{BASE_URL}/{token}"
    return render_template("link.html", link=link)


@app.route("/<token>")
def read_secret(token):
    value = store.read(token)
    if value is None:
        return render_template(
            "secret.html",
            secret="Dieses Passwort ist nicht mehr gueltig.",
        )
    return render_template("secret.html", secret=value)


@app.route("/secret/<token>")
def redirect_old(token):
    return redirect(f"/{token}", code=302)


@app.route("/logo")
def logo():
    custom_logo = os.path.join(DATA_DIR, "logo.png")
    if os.path.exists(custom_logo):
        return send_file(custom_logo)
    return send_from_directory("static", "logo.png")


@app.route("/admin/", methods=["GET", "POST"])
def admin_root():
    if request.method == "POST":
        _check_csrf()

    # 1) Noch kein Admin-Passwort gesetzt -> Setup-Seite
    if not is_admin_password_set():
        error = ""

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            pw1 = (request.form.get("password") or "").strip()
            pw2 = (request.form.get("password_confirm") or "").strip()

            if not username:
                error = "Bitte einen Benutzernamen eingeben."
            elif len(username) < 3:
                error = "Benutzername muss mindestens 3 Zeichen haben."
            elif not pw1:
                error = "Bitte ein Passwort eingeben."
            elif pw1 != pw2:
                error = "Passwoerter stimmen nicht ueberein."
            elif len(pw1) < 8:
                error = "Passwort muss mindestens 8 Zeichen haben."
            else:
                set_admin_credentials(username, pw1)
                session["admin"] = True
                session["last_activity"] = time.time()
                session["login_failures"] = 0
                return redirect(url_for("admin_root"))

        return render_template("admin_setup.html", error=error)

    # 2) Passwort ist gesetzt, aber nicht eingeloggt -> Login
    if not session.get("admin"):
        error = ""

        failures = session.get("login_failures", 0)
        if failures >= 5:
            error = "Zu viele Fehlversuche. Bitte spaeter erneut versuchen."
            return render_template("admin_login.html", error=error)

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            pw = (request.form.get("password") or "").strip()

            cfg = _load_admin_config()
            stored_username = cfg.get("username") or FIXED_ADMIN_USER

            if (
                username
                and username == stored_username
                and verify_admin_password(pw)
            ):
                session["admin"] = True
                session["last_activity"] = time.time()
                session["login_failures"] = 0
                return redirect(url_for("admin_root"))
            else:
                session["login_failures"] = failures + 1
                error = "Benutzername oder Passwort ist falsch."

        return render_template("admin_login.html", error=error)

    # 3) Eingeloggt -> Konfigseite
    message = ""
    error = ""

    if request.method == "POST":
        action = request.form.get("action") or ""

        if action == "change_password":
            old_pw = (request.form.get("old_password") or "").strip()
            new_pw1 = (request.form.get("new_password") or "").strip()
            new_pw2 = (request.form.get("new_password_confirm") or "").strip()

            if not old_pw or not new_pw1 or not new_pw2:
                error = "Bitte alle Passwortfelder ausfuellen."
            elif not verify_admin_password(old_pw):
                error = "Altes Passwort ist falsch."
            elif new_pw1 != new_pw2:
                error = "Neue Passwoerter stimmen nicht ueberein."
            elif len(new_pw1) < 8:
                error = "Neues Passwort muss mindestens 8 Zeichen haben."
            else:
                set_admin_password(new_pw1)
                message = "Admin Passwort wurde geaendert."

        elif action == "factory_reset":
            try:
                store.clear_all()
            except Exception:
                pass

            try:
                if os.path.exists(ADMIN_CONFIG_FILE):
                    os.remove(ADMIN_CONFIG_FILE)
            except Exception:
                pass

            try:
                logo_path = os.path.join(DATA_DIR, "logo.png")
                if os.path.exists(logo_path):
                    os.remove(logo_path)
            except Exception:
                pass

            session.clear()
            return redirect(url_for("admin_root"))

        else:
            file = request.files.get("logo")
            if file and file.filename:
                save_path = os.path.join(DATA_DIR, "logo.png")
                file.save(save_path)
                message = "Logo wurde aktualisiert."
            else:
                error = "Keine Datei ausgewaehlt."

    cfg = _load_admin_config()
    username = cfg.get("username") or FIXED_ADMIN_USER

    latest_tag = get_latest_docker_hub_version()
    latest_version = None
    update_available = False

    if latest_tag:
        latest_version = latest_tag
        try:
            current_parsed = _parse_version(VERSION)
            latest_parsed = _parse_version(latest_tag)
            if latest_parsed > current_parsed:
                update_available = True
        except Exception:
            update_available = False

    return render_template(
        "admin_config.html",
        message=message,
        error=error,
        username=username,
        version=VERSION,
        latest_version=latest_version,
        update_available=update_available,
    )


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.pop("admin", None)
    session.pop("last_activity", None)
    return redirect(url_for("admin_root"))
