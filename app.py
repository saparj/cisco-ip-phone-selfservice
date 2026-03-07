from flask import Flask, Response, request, abort, redirect, url_for
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

APP_VERSION = "0.2.0"

PHONE_UI_TITLE = "UC Self-Service"
PHONE_UI_SUBTITLE = "IP Phone Requests"
PHONE_UI_HOME_LABEL = "Home"
PHONE_UI_BACK_LABEL = "Back"
PHONE_UI_EXIT_LABEL = "Exit"

load_dotenv()

app = Flask(__name__)

DB_PATH = Path(os.getenv("DB_PATH", "/var/lib/phone-services/requests.db"))
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

def _existing_columns(con) -> set[str]:
    rows = con.execute("PRAGMA table_info(requests)").fetchall()
    return {r[1] for r in rows}

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                source_ip TEXT,
                user_agent TEXT,
                kind TEXT NOT NULL,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                approved_by TEXT,
                approved_at TEXT,
                completed_at TEXT,
                rejected_reason TEXT
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")

        cols = _existing_columns(con)
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

        con.commit()

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
            cur.execute(
                "UPDATE requests SET status=?, updated_at=?, approved_by=?, approved_at=? WHERE id=?",
                (target_status, now, actor, now, request_id),
            )
        elif target_status == STATUS_REJECTED:
            rr = (reject_reason or "").strip()
            if not rr:
                return False, "Reject requires a reason"
            cur.execute(
                "UPDATE requests SET status=?, updated_at=?, rejected_reason=? WHERE id=?",
                (target_status, now, rr, request_id),
            )
        elif target_status == STATUS_COMPLETED:
            cur.execute(
                "UPDATE requests SET status=?, updated_at=?, completed_at=? WHERE id=?",
                (target_status, now, now, request_id),
            )
        else:
            cur.execute(
                "UPDATE requests SET status=?, updated_at=? WHERE id=?",
                (target_status, now, request_id),
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

def phone_softkeys(*, back_url: str | None = None) -> str:
    keys = []
    pos = 1
    if back_url:
        keys.append(f"""  <SoftKeyItem>
    <Name>{PHONE_UI_BACK_LABEL}</Name>
    <URL>{back_url}</URL>
    <Position>{pos}</Position>
  </SoftKeyItem>""")
        pos += 1

    keys.append(f"""  <SoftKeyItem>
    <Name>{PHONE_UI_HOME_LABEL}</Name>
    <URL>{BASE_URL}/phone/menu</URL>
    <Position>{pos}</Position>
  </SoftKeyItem>""")
    pos += 1

    keys.append(f"""  <SoftKeyItem>
    <Name>{PHONE_UI_EXIT_LABEL}</Name>
    <URL>{BASE_URL}/phone/quit</URL>
    <Position>3</Position>
  </SoftKeyItem>""")
    return "\n".join(keys)


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
            "SELECT id, created_at, kind, status, details FROM requests WHERE source_ip=? ORDER BY id DESC LIMIT 10",
            (source_ip,),
        ).fetchall()

    items = []
    for rid, _, _, status, details_text in rows:
        # Compact, readable summary. Avoid coupling too tightly to JSON structure.
        dn = ""
        try:
            d = json.loads(details_text or "{}")
            dn = d.get("dn") or (d.get("request") or {}).get("dn") or ""
        except Exception:
            dn = ""

        # Keep it short for phone screens
        label_bits = [f"#{rid}", status]
        if dn:
            label_bits.append(dn)
        label = " ".join(label_bits)

        # MenuItem URL: keep it simple for v0.2.0
        # For now, selecting an item shows a small detail screen.
        items.append(
            f"""  <MenuItem>
    <Name>{x(label)}</Name>
    <URL>{BASE_URL}/phone/recent/{rid}</URL>
  </MenuItem>"""
        )

    if not items:
        items.append(
            f"""  <MenuItem>
    <Name>{x("No requests yet")}</Name>
    <URL>{BASE_URL}/phone/menu</URL>
  </MenuItem>"""
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneMenu>
  <Title>My Requests</Title>
  <Prompt>Last 10 from this phone/IP</Prompt>
{chr(10).join(items)}

  {phone_softkeys()}
</CiscoIPPhoneMenu>"""

    return xml_response(xml)


@app.get("/phone/recent/<int:rid>")
def phone_recent_detail(rid: int):
    source_ip = request.headers.get("X-Real-IP", request.remote_addr)

    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT id, created_at, kind, status, details FROM requests WHERE id=? AND source_ip=?",
            (rid, source_ip),
        ).fetchone()

    if row is None:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Not Found</Title>
  <Text>Request not found.</Text>

  {phone_softkeys(back_url=f"{BASE_URL}/phone/recent")}
</CiscoIPPhoneText>"""
        return xml_response(xml)

    # Build a readable detail text with minimal coupling to JSON
    dn = rn = why = ""
    try:
        d = json.loads(row["details"] or "{}")
        dn = d.get("dn") or (d.get("request") or {}).get("dn") or ""
        rn = d.get("requested_name") or (d.get("request") or {}).get("requested_name") or ""
        why = d.get("why") or (d.get("request") or {}).get("why") or ""
    except Exception:
        pass

    lines = [
        f"ID: #{row['id']}",
        f"Status: {row['status']}",
        f"Kind: {row['kind']}",
        f"Created: {row['created_at']}",
    ]
    if dn:
        lines.append(f"DN: {dn}")
    if rn:
        lines.append(f"Name: {rn}")
    if why:
        lines.append(f"Why: {why}")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneText>
  <Title>Request #{row['id']}</Title>
  <Text>{x(chr(10).join(lines))}</Text>

  {phone_softkeys(back_url=f"{BASE_URL}/phone/recent")}
</CiscoIPPhoneText>"""

    return xml_response(xml)


@app.get("/phone/dnlabel")
def phone_dnlabel():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CiscoIPPhoneInput>
  <Title>Update Display Name</Title>
  <Prompt>Enter DN and new name</Prompt>
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


def admin_css() -> str:
    return """
    :root{
      --bg:#ffffff; --fg:#111; --muted:#555; --card:#f6f6f6; --border:#ddd; --pill:#eee;
      --link:#0b57d0;

      --pending-bg:#fff4cc;
      --pending-fg:#7a5d00;

      --approved-bg:#e6f4ea;
      --approved-fg:#1e7e34;

      --rejected-bg:#fde7e9;
      --rejected-fg:#a61b29;

      --completed-bg:#e8f0fe;
      --completed-fg:#174ea6;
    }
    @media (prefers-color-scheme: dark){
      :root{
        --bg:#0f1115; --fg:#e7e7e7; --muted:#a8a8a8; --card:#1a1f27; --border:#2a3340; --pill:#232a35;
        --link:#8ab4f8;

        --pending-bg:#3a2f00;
        --pending-fg:#ffd966;

        --approved-bg:#0f2f1f;
        --approved-fg:#7ee2a8;

        --rejected-bg:#3a161a;
        --rejected-fg:#ff9aa2;

        --completed-bg:#14233b;
        --completed-fg:#9cc3ff;
      }
    }
    body{
      font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      margin:20px;background:var(--bg);
      color:var(--fg);
      line-height:1.4;
    }
    a{color:var(--link);text-decoration:none;}
    a:hover{text-decoration:underline;}
    a:focus-visible, button:focus-visible, input:focus-visible{outline:2px solid var(--link); outline-offset:2px;}
    h1{margin:0 0 6px 0;}
    .meta{color:var(--muted);margin:0 0 10px 0;}
    .topbar{margin:0 0 16px 0;color:var(--muted);}
    table{border-collapse:collapse;width:100%;}
    th,td{border:1px solid var(--border);padding:8px;vertical-align:top;}
    th{background:var(--card);text-align:left;}
    table tr:first-child th{border-bottom:2px solid var(--border);}
    tr:hover td{background:var(--card);}
    code{white-space:nowrap;}
    pre, code{overflow:auto;}
    .actions form{display:inline;margin:0 6px 6px 0;}
    .inline-form{
      display:inline-flex;
      align-items:center;
      gap:6px;
      margin:0 6px 6px 0;
    }
    input[type=text]{
      padding:6px;
      width:160px;
      background:var(--bg);
      color:var(--fg);
      border:1px solid var(--border);
      border-radius:8px;
    }
    button{
      padding:6px 10px;
      cursor:pointer;
      background:var(--card);
      color:var(--fg);
      border:1px solid var(--border);
      border-radius:8px;
    }
    .pill{
      padding:2px 8px;
      border-radius:999px;
      background:var(--pill);
      display:inline-block;
      font-weight:600;
      font-size:0.85em;
    }
    .pill.pending{background:var(--pending-bg);color:var(--pending-fg);}
    .pill.approved{background:var(--approved-bg);color:var(--approved-fg);}
    .pill.rejected{background:var(--rejected-bg);color:var(--rejected-fg);}
    .pill.completed{background:var(--completed-bg);color:var(--completed-fg);}
    """


# --- Admin HTML helpers (no template engine; escape explicitly) ---
def h(s: object) -> str:
    """Escape text for safe insertion into HTML."""
    return html.escape("" if s is None else str(s), quote=True)

def code(s: object) -> str:
    """Inline code formatting (escaped)."""
    return f"<code>{h(s)}</code>"

def pill(label: object, cls: str = "") -> str:
    """Generic pill/badge (escaped label)."""
    cls_attr = f"pill {cls}".strip() if cls else "pill"
    return f"<span class='{h(cls_attr)}'>{h(label)}</span>"

def status_pill(status: str) -> str:
    """Status pill. Returns safe HTML; do not wrap in h()."""
    s = (status or "").strip().lower()
    cls = s if s in ("pending", "approved", "rejected", "completed") else "pending"
    return pill(status, cls)

def td_html(inner_html: str) -> str:
    """Table cell for already-safe HTML."""
    return f"<td>{inner_html}</td>"

def td_text(val: object) -> str:
    """Table cell for raw values (escaped)."""
    return f"<td>{h(val)}</td>"

def th_text(label: str) -> str:
    return f"<th>{h(label)}</th>"

def tr(*cells_html: str) -> str:
    """Row from already-built <td>/<th> strings."""
    return "<tr>" + "".join(cells_html) + "</tr>"

def post_button(action_url: str, label: str) -> str:
    """POST form button. action_url comes from url_for()."""
    return (
        f"<form method='post' action='{h(action_url)}'>"
        f"<button type='submit'>{h(label)}</button></form>"
    )

def post_reject_form(action_url: str) -> str:
    return (
        f"<form method='post' action='{h(action_url)}' class='inline-form'>"
        "<input type='text' name='reason' placeholder='Reject reason' required>"
        "<button type='submit'>Reject</button></form>"
    )


@app.get("/admin/dashboard")
@require_admin
def admin_dashboard():
    # Simple HTML dashboard, no JS frameworks. Actions POST to existing endpoints.
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT
              id, created_at, updated_at, kind, status, source_ip, approved_by,
              approved_at, completed_at, rejected_reason, details
            FROM requests
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

    def summary(details_text: str) -> str:
        # details is JSON-in-TEXT; show a compact summary without coupling too hard to schema
        try:
            d = json.loads(details_text or "{}")
            dn = d.get("dn") or (d.get("request") or {}).get("dn")
            rn = d.get("requested_name") or (d.get("request") or {}).get("requested_name")
            why = d.get("why") or (d.get("request") or {}).get("why")
            bits = []
            if dn:
                bits.append(f"DN: {dn}")
            if rn:
                bits.append(f"Name: {rn}")
            if why:
                bits.append(f"Why: {why}")
            return " | ".join(bits) if bits else "—"
        except Exception:
            return "—"

    def audit_block(r: sqlite3.Row) -> str:
        """Return safe HTML for the Audit column."""
        bits: list[str] = []
        if r["approved_by"]:
            bits.append(f"approved_by={r['approved_by']}")
        if r["rejected_reason"]:
            bits.append(f"rejected_reason={r['rejected_reason']}")
        if r["completed_at"]:
            bits.append(f"completed_at={r['completed_at']}")
        # Escape once when rendering; use <br> for readability.
        if not bits:
            return "—"
        return "<br>".join(h(b) for b in bits)

    css = admin_css()

    lines: list[str] = []
    lines.append("<!doctype html>")
    lines.append("<html><head>")
    lines.append("<meta charset='utf-8'>")
    lines.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    lines.append(f"<title>Admin Dashboard</title><style>{css}</style></head><body>")
    lines.append("<h1>Admin Dashboard</h1>")
    lines.append(
        "<div class='topbar'>"
        "<a href='/admin/health'>Health</a> · "
        "<a href='/admin/list'>Text view</a>"
        "</div>"
    )
    lines.append(f"<p class='meta'>Signed in as <b>{h(current_actor())}</b> · Showing newest 50 requests (older requests not shown)</p>")

    lines.append("<table>")
    lines.append(
        tr(
            th_text("ID"),
            th_text("Status"),
            th_text("Created"),
            th_text("Kind"),
            th_text("Summary"),
            th_text("Audit"),
            th_text("Actions"),
        )
    )

    for r in rows:
        rid = r["id"]
        status = r["status"]

        actions: list[str] = ["<div class='actions'>"]
        if status == STATUS_PENDING:
            actions.append(post_button(url_for("admin_approve", rid=rid), "Approve"))
            actions.append(post_reject_form(url_for("admin_reject", rid=rid)))
        elif status == STATUS_APPROVED:
            actions.append(post_button(url_for("admin_complete", rid=rid), "Complete"))
        else:
            actions.append(pill("No actions"))
        actions.append("</div>")

        lines.append(
            tr(
                td_html(code(rid)),
                td_html(status_pill(status)),
                td_text(r["created_at"]),
                td_text(r["kind"]),
                td_text(summary(r["details"])),
                td_html(audit_block(r)),
                td_html("".join(actions)),
            )
        )

    lines.append("</table>")
    lines.append("</body></html>")

    return Response("\n".join(lines), mimetype="text/html")


@app.get("/admin/health")
@require_admin
def admin_health():
    # Mirror /health data, but render it as an admin-friendly page.
    status = "ok"
    db_status = "ok"
    try:
        with sqlite3.connect(DB_PATH) as con:
            con.execute("SELECT 1").fetchone()
    except Exception:
        status = "degraded"
        db_status = "error"

    payload = {
        "status": status,
        "version": APP_VERSION,
        "db": db_status,
        "timestamp": utc_now(),
    }

    css = admin_css()
    
    pretty = h(json.dumps(payload, indent=2))

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Health</title>
  <style>
{css}
.card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px;margin:12px 0;}}
.kv{{display:grid;grid-template-columns:160px 1fr;gap:8px 12px;}}
.k{{color:var(--muted);}}
  </style>
</head>
<body>
  <h1>Health</h1>
  <p class="topbar"><a href="/admin/dashboard">← Back to dashboard</a></p>

  <div class="card">
    <div class="kv">
      <div class="k">Status</div><div>{h(payload["status"])}</div>
      <div class="k">Version</div><div>{h(payload["version"])}</div>
      <div class="k">Database</div><div>{h(payload["db"])}</div>
      <div class="k">Timestamp</div><div>{h(payload["timestamp"])}</div>
    </div>
  </div>

  <h2 style="margin-top:18px;">Raw</h2>
  <pre>{pretty}</pre>
</body>
</html>"""

    return Response(html_doc, mimetype="text/html")


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
    _apply_transition(
        request_id=rid,
        target_status=STATUS_APPROVED,
        actor=current_actor(),
    )
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/reject/<int:rid>")
@require_admin
def admin_reject(rid: int):
    reason = (request.values.get("reason") or "").strip()
    if not reason:
        return redirect(url_for("admin_dashboard"))
    
    _apply_transition(
        request_id=rid,
        target_status=STATUS_REJECTED,
        actor=current_actor(),
        reject_reason=reason,
    )
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/complete/<int:rid>")
@require_admin
def admin_complete(rid: int):
    _apply_transition(
        request_id=rid,
        target_status=STATUS_COMPLETED,
        actor=current_actor(),
    )
    return redirect(url_for("admin_dashboard"))


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
