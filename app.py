from flask import Flask, Response, request
import sqlite3
from datetime import datetime
from pathlib import Path
from werkzeug.exceptions import HTTPException
import html
import os
from dotenv import load_dotenv
import json

APP_VERSION = "0.2.0-dev"

load_dotenv()

app = Flask(__name__)

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).with_name("tickets.db")))
BASE_URL = os.getenv("BASE_URL", "http://example.local")

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
  <Title>Lab Tickets</Title>
  <Prompt>Select an option</Prompt>

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
    DEFAULT_PT = "INTERNAL_PT"

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

    pt = DEFAULT_PT

    source_ip = request.headers.get("X-Real-IP", request.remote_addr)
    user_agent = request.headers.get("User-Agent", "")

    details = f"DN={dn}, PT={pt}, requested_name={requested_name}, why={why}"

    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()

        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

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
def admin_list():
    with sqlite3.connect(DB_PATH) as con:
        rows = con.execute(
            "SELECT id, created_at, source_ip, kind, status, details FROM requests ORDER BY id DESC LIMIT 50"
        ).fetchall()

    lines = ["id | created_at | source_ip | kind | status | details"]
    for r in rows:
        lines.append(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}")
    return "<pre>" + "\n".join(lines) + "</pre>"


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
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    return Response(
        json.dumps(payload),
        status=200 if status == "ok" else 503,
        content_type="application/json",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
