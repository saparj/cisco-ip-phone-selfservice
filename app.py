from flask import Flask, Response, request, abort
import sqlite3
from datetime import datetime
from pathlib import Path
from werkzeug.exceptions import HTTPException
import html
import os
from dotenv import load_dotenv
import json
import re
from functools import wraps

APP_VERSION = "0.2.0-dev"

PHONE_UI_TITLE = "UC Self-Service"
PHONE_UI_SUBTITLE = "IP Phone Requests"

load_dotenv()

app = Flask(__name__)

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).with_name("tickets.db")))
BASE_URL = os.getenv("BASE_URL", "http://example.local")
ADMIN_USERS = set(
    u.strip()
    for u in os.getenv("ADMIN_USERS", "admin").split(",")
    if u.strip()
)

# --- Workflow states (v0.2.0) ---

STATUS_PENDING = "Pending"
STATUS_APPROVED = "Approved"
STATUS_REJECTED = "Rejected"
STATUS_COMPLETED = "Completed"

ALLOWED_TRANSITIONS = {
    STATUS_PENDING: {STATUS_APPROVED, STATUS_REJECTED},
    STATUS_APPROVED: {STATUS_COMPLETED},
    STATUS_REJECTED: set(),
    STATUS_COMPLETED: set(),
}

VALID_STATUSES = set(ALLOWED_TRANSITIONS.keys())

def _can_transition(current_status: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current_status, set())

def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def build_details_phone_name_update(dn: str, requested_name: str, why: str) -> dict:
    return {
        "schema_version": 1,
        "dn": dn,
        "requested_name": requested_name,
        "why": why,
    }

def current_actor() -> str:
    # Provided by nginx basic auth via proxy_set_header
    return request.headers.get("X-Remote-User") or "unknown"

def _existing_columns(con, table_name: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_ip TEXT,
                user_agent TEXT,
                kind TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")

        # v0.2.0 schema upgrades (idempotent)
        cols = _existing_columns(con, "requests")
        if "updated_at" not in cols:
            con.execute("ALTER TABLE requests ADD COLUMN updated_at TEXT")
        if "approved_by" not in cols:
            con.execute("ALTER TABLE requests ADD COLUMN approved_by TEXT")
        if "approved_at" not in cols:
            con.execute("ALTER TABLE requests ADD COLUMN approved_at TEXT")
        if "completed_at" not in cols:
            con.execute("ALTER TABLE requests ADD COLUMN completed_at TEXT")
        if "rejected_reason" not in cols:
            con.execute("ALTER TABLE requests ADD COLUMN rejected_reason TEXT")

init_db()


def _apply_transition(
    request_id: int,
    target_status: str,
    actor: str,
    reject_reason: str | None = None,
) -> tuple[bool, str]:
    """
    Returns (ok, message). Writes status + audit fields atomically.
    """

    if target_status not in VALID_STATUSES:
        return False, f"Invalid target status: {target_status}"

    now = utc_now()

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        row = cur.execute(
            "SELECT id, status FROM requests WHERE id = ?",
            (request_id,),
        ).fetchone()

        if row is None:
            return False, f"Request {request_id} not found"

        current = row["status"]

        if current not in VALID_STATUSES:
            return False, f"Request {request_id} has unknown status: {current}"

        if not _can_transition(current, target_status):
            return False, f"Invalid transition: {current} -> {target_status}"

        # Build the update dynamically so we only set relevant audit fields
        fields = ["status = ?", "updated_at = ?"]
        params: list[object] = [target_status, now]

        if target_status == STATUS_APPROVED:
            fields += ["approved_by = ?", "approved_at = ?"]
            params += [actor, now]

        elif target_status == STATUS_REJECTED:
            rr = (reject_reason or "").strip()
            if not rr:
                return False, "Reject requires a reason"
            fields += ["rejected_reason = ?"]
            params += [rr]

        elif target_status == STATUS_COMPLETED:
            fields += ["completed_at = ?"]
            params += [now]

        params.append(request_id)

        cur.execute(
            f"UPDATE requests SET {', '.join(fields)} WHERE id = ?",
            params,
        )

    return True, "ok"

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = request.headers.get("X-Remote-User")

        # Must be authenticated via Nginx
        if not user:
            abort(403)

        # Must be an allowed admin
        if user not in ADMIN_USERS:
            abort(403)

        return f(*args, **kwargs)

    return wrapper

def xml_response(xml: str) -> Response:
    # Cisco phones can be picky; keep it simple.
    return Response(xml + "\n", content_type="text/xml")

def x(text: str) -> str:
    # XML-escape content
    return html.escape(text or "", quote=True)


@app.errorhandler(Exception)
def handle_all_errors(e):
    # Always return Cisco XML for phone endpoints
    if request.path.startswith("/phone/"):
        code = 500
        if isinstance(e, HTTPException):
            code = e.code or 500

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Error</Title>
  <Text>{x(f"{code} {type(e).__name__}: {str(e)}")}</Text>
</CiscoIPPhoneText>"""
        return xml_response(xml), code

    # For non-phone endpoints, return normal HTTP errors without recursion
    if isinstance(e, HTTPException):
        return e  # lets Flask render the correct status code
    return "Internal Server Error", 500


@app.get("/phone/menu")
def phone_menu():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneMenu>
  <Title>{PHONE_UI_TITLE}</Title>
  <Prompt>{PHONE_UI_SUBTITLE}</Prompt>

  <MenuItem>
    <Name>My recent requests</Name>
    <URL>{BASE_URL}/phone/recent</URL>
  </MenuItem>

  <MenuItem>
    <Name>Request Phone Name Update</Name>
    <URL>{BASE_URL}/phone/phonename/info</URL>
  </MenuItem>

  <MenuItem>
    <Name>Exit</Name>
    <URL>{BASE_URL}/phone/quit</URL>
  </MenuItem>
</CiscoIPPhoneMenu>"""
    return xml_response(xml)


@app.get("/phone/phonename/info")
def phone_phonename_info():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Phone Name Update</Title>
  <Text>Updates phone display name, caller ID name, and directory record. Approval required.</Text>

  <SoftKeyItem>
    <Name>Continue</Name>
    <URL>{BASE_URL}/phone/dnlabel</URL>
    <Position>1</Position>
  </SoftKeyItem>
  <SoftKeyItem>
    <Name>Back</Name>
    <URL>{BASE_URL}/phone/menu</URL>
    <Position>2</Position>
  </SoftKeyItem>
  <SoftKeyItem>
    <Name>Exit</Name>
    <URL>{BASE_URL}/phone/quit</URL>
    <Position>3</Position>
  </SoftKeyItem>
</CiscoIPPhoneText>"""
    return xml_response(xml)


@app.get("/phone/recent")
def phone_recent():
    # Show last 10 requests by source IP (simple lab identity)
    source_ip = request.headers.get("X-Real-IP", request.remote_addr)

    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT id, created_at, kind, status FROM requests WHERE source_ip=? ORDER BY id DESC LIMIT 10",
            (source_ip,),
        ).fetchall()

    items = []
    for rid, created_at, kind, status in rows:
        # Put ALL readable info in Name
        display = f"#{rid} {status} {kind} {created_at}"

        items.append(
            f"""  <DirectoryEntry>
    <Name>{x(display)}</Name>
    <Telephone></Telephone>
  </DirectoryEntry>"""
        )

    if not items:
        items.append(
            """  <DirectoryEntry>
    <Name>No requests yet</Name>
    <Telephone></Telephone>
  </DirectoryEntry>"""
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneDirectory>
  <Title>My Requests</Title>
  <Prompt>Last 10 from this phone/IP</Prompt>
{chr(10).join(items)}
</CiscoIPPhoneDirectory>"""

    return xml_response(xml)


@app.get("/phone/dnlabel")
def phone_dnlabel():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneInput>
  <Title>Phone Name Update</Title>
  <Prompt>Enter DN and requested name</Prompt>
  <URL>{BASE_URL}/phone/submit_dnlabel</URL>

  <InputItem>
    <DisplayName>DN</DisplayName>
    <QueryStringParam>dn</QueryStringParam>
    <InputFlags>N</InputFlags>
  </InputItem>

  <InputItem>
    <DisplayName>Requested name</DisplayName>
    <QueryStringParam>requestedName</QueryStringParam>
    <InputFlags>A</InputFlags>
  </InputItem>
  
  <InputItem>
    <DisplayName>Justification</DisplayName>
    <QueryStringParam>why</QueryStringParam>
    <InputFlags>A</InputFlags>
  </InputItem>
</CiscoIPPhoneInput>"""
    return xml_response(xml)


@app.route("/phone/submit_dnlabel", methods=["GET", "POST"])
def phone_submit_dnlabel():
    MAX_NAME_LEN = 32  # arbitrary limit to keep details reasonably sized
    MAX_JUSTIFICATION_LEN = 256

    dn_patterns = [
        r"^1[2-9]\d{2}[2-9]\d{6}$", # Country code + 10 digit number
        r"^[2-9]\d{2}[2-9]\d{6}$",   # 10 digit number
        r"^[2-9]\d{6}$",             # 7 digit number
        r"^\d{4}$",               # 4 digit short extension
    ]

    dn = (request.values.get("dn") or "").strip()
    requested_name = (request.values.get("requestedName") or "").strip()
    why = (request.values.get("why") or "").strip()

    if not dn or not requested_name:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Error</Title>
  <Text>DN and Requested name are required.</Text>
</CiscoIPPhoneText>"""
        return xml_response(xml)
    
    if not any(re.fullmatch(pattern, dn) for pattern in dn_patterns):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Error</Title>
  <Text>DN not in valid format.</Text>
</CiscoIPPhoneText>"""
        return xml_response(xml)
    
    if len(requested_name) > MAX_NAME_LEN:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Error</Title>
  <Text>Requested name is too long (max {MAX_NAME_LEN} characters).</Text>
</CiscoIPPhoneText>"""
        return xml_response(xml)

    if len(why) > MAX_JUSTIFICATION_LEN:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Error</Title>
  <Text>Justification is too long (max {MAX_JUSTIFICATION_LEN} characters).</Text>
</CiscoIPPhoneText>"""
        return xml_response(xml)

    source_ip = request.headers.get("X-Real-IP", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "")

    payload = build_details_phone_name_update(
        dn=dn,
        requested_name=requested_name,
        why=why,
    )
    payload["requester"] = {
        "ip": source_ip,
        "user_agent": user_agent,
        "device_name": None, # future: phone hostname
    }
    details = json.dumps(payload, ensure_ascii=False)

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()

        now = utc_now()

        cur.execute(
            """
            INSERT INTO requests(
                created_at,
                updated_at,
                source_ip,
                user_agent,
                kind,
                details
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                now,
                now,
                source_ip,
                user_agent,
                "PHONE_NAME_UPDATE",
                details,
            ),
        )

        rid = cur.lastrowid

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Submitted</Title>
  <Text>Phone name update request #{rid} created (Pending).</Text>
  
  <SoftKeyItem>
    <Name>Home</Name>
    <URL>{BASE_URL}/phone/menu</URL>
    <Position>1</Position>
  </SoftKeyItem>
  <SoftKeyItem>
    <Name>My Requests</Name>
    <URL>{BASE_URL}/phone/recent</URL>
    <Position>2</Position>
  </SoftKeyItem>
  <SoftKeyItem>
    <Name>Exit</Name>
    <URL>{BASE_URL}/phone/quit</URL>
    <Position>3</Position>
  </SoftKeyItem>
  
</CiscoIPPhoneText>"""
    return xml_response(xml)


@app.get("/phone/quit")
def phone_quit():
    # Force the phone out of the service and back to the Services/Applications screen.
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneExecute>
  <ExecuteItem URL="Init:Services"/>
</CiscoIPPhoneExecute>"""
    return xml_response(xml)


@app.get("/admin/list")
@require_admin
def admin_list():
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT id, created_at, updated_at, approved_by,
                   approved_at, completed_at, rejected_reason,
                   source_ip, kind, status, details
            FROM requests
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

    def s(val: object) -> str:
        return "" if val is None else str(val)

    def trunc(text: str, n: int) -> str:
        return text if len(text) <= n else text[: n - 1] + "…"

    header = (
        f"{'ID':>4}  {'STATUS':<10}  {'CREATED':<20}  {'UPDATED':<20}  "
        f"{'KIND':<18}  {'SRC_IP':<15}  {'APPROVED_BY':<12}  {'REJECT':<18}  {'DETAILS':<60}"
    )
    lines = [header, "-" * len(header)]

    for r in rows:
        lines.append(
            f"{r['id']:>4}  "
            f"{trunc(s(r['status']), 10):<10}  "
            f"{trunc(s(r['created_at']), 20):<20}  "
            f"{trunc(s(r['updated_at']), 20):<20}  "
            f"{trunc(s(r['kind']), 18):<18}  "
            f"{trunc(s(r['source_ip']), 15):<15}  "
            f"{trunc(s(r['approved_by']), 12):<12}  "
            f"{trunc(s(r['rejected_reason']), 18):<18}  "
            f"{trunc(s(r['details']), 60):<60}"
        )

    escaped_report = html.escape("\n".join(lines))
    return Response("<pre>" + escaped_report + "</pre>", mimetype="text/html")


@app.post("/admin/approve/<int:rid>")
@require_admin
def admin_approve(rid: int):
    ok, msg = _apply_transition(
        request_id=rid,
        target_status=STATUS_APPROVED,
        actor=current_actor(),
    )
    code = 200 if ok else 400
    return Response(f"<pre>{'OK' if ok else 'ERROR'}: {msg}</pre>", status=code)


@app.post("/admin/reject/<int:rid>")
@require_admin
def admin_reject(rid: int):
    reason = (request.values.get("reason") or "").strip()
    ok, msg = _apply_transition(
        request_id=rid,
        target_status=STATUS_REJECTED,
        actor=current_actor(),
        reject_reason=reason,
    )
    code = 200 if ok else 400
    return Response(f"<pre>{'OK' if ok else 'ERROR'}: {msg}</pre>", status=code)


@app.post("/admin/complete/<int:rid>")
@require_admin
def admin_complete(rid: int):
    ok, msg = _apply_transition(
        request_id=rid,
        target_status=STATUS_COMPLETED,
        actor=current_actor(),
    )
    code = 200 if ok else 400
    return Response(f"<pre>{'OK' if ok else 'ERROR'}: {msg}</pre>", status=code)


@app.get("/health")
def health():
    status = "ok"
    db_status = "ok"

    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("SELECT 1")
    except Exception:
        db_status = "error"
        status = "degraded"

    payload = {
        "status": status,
        "version": APP_VERSION,
        "db": db_status,
        "timestamp": utc_now(),
    }

    return Response(
        json.dumps(payload),
        status=200 if status == "ok" else 503,
        content_type="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
