import os
import sys
import subprocess
from pathlib import Path
import hmac

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse

import json
import logging

from urllib.parse import urlparse

logging.basicConfig(level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
logger = logging.getLogger("worker")
logger.setLevel(logging.DEBUG)
print(logging.getLogger().level)

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
def index():
    output_dir = OUTPUT_DIR

    reports = []

    if output_dir.exists():
        for year_dir in sorted(output_dir.iterdir()):
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            year = year_dir.name
            report = year_dir / f"report_{year}.html"
            auswertung = year_dir / f"auswertung_{year}.json"

            reports.append({
                "year": year,
                "report_exists": report.exists(),
                "json_exists": auswertung.exists(),
            })

    rows = ""

    for r in reports:
        report_link = (
            f'<a href="/reports/{r["year"]}/html">HTML öffnen</a>'
            if r["report_exists"]
            else "kein HTML"
        )
        json_link = (
            f'<a href="/reports/{r["year"]}/json">JSON öffnen</a>'
            if r["json_exists"]
            else "kein JSON"
        )

        rows += f"""
        <tr>
          <td>{r["year"]}</td>
          <td>{report_link}</td>
          <td>{json_link}</td>
        </tr>
        """

    return f"""
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Prämienauswertung</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      margin: 2rem;
      background: #f6f7f9;
      color: #111827;
    }}
    .card {{
      background: white;
      border-radius: 14px;
      padding: 1.5rem;
      max-width: 900px;
      box-shadow: 0 1px 5px rgba(0,0,0,.08);
    }}
    h1 {{ margin-top: 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }}
    th, td {{
      padding: .8rem;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
    }}
    th {{
      background: #111827;
      color: white;
    }}
    a {{
      color: #2563eb;
      font-weight: 600;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Prämienauswertung</h1>
    <p>Verfügbare Jahresreports</p>

    <table>
      <thead>
        <tr>
          <th>Jahr</th>
          <th>HTML Report</th>
          <th>JSON Auswertung</th>
        </tr>
      </thead>
      <tbody>
        {rows if rows else '<tr><td colspan="3">Noch keine Auswertungen vorhanden.</td></tr>'}
      </tbody>
    </table>
  </div>
</body>
</html>
"""


@app.get("/reports/{year}/html")
def report_html(year: int):
    path = OUTPUT_DIR / str(year) / f"report_{year}.html"

    if not path.exists():
        raise HTTPException(status_code=404, detail="HTML-Report nicht gefunden")

    return FileResponse(path, media_type="text/html")


@app.get("/reports/{year}/json")
def report_json(year: int):
    path = OUTPUT_DIR / str(year) / f"auswertung_{year}.json"

    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON-Auswertung nicht gefunden")

    return FileResponse(path, media_type="application/json")
PAPERLESS_URL = os.environ["PAPERLESS_URL"].rstrip("/")
PAPERLESS_TOKEN = os.environ["PAPERLESS_TOKEN"]
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data"))

HEADERS = {"Authorization": f"Token {PAPERLESS_TOKEN}"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def extract_id(url: str) -> int:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")

    if not parts or not parts[-1].isdigit():
        raise ValueError("Keine gültige numerische ID am Ende der URL")

    return int(parts[-1])



def get_document(document_id: int) -> dict:

    r = requests.get(
        f"{PAPERLESS_URL}/api/documents/{document_id}/",
        headers=HEADERS,
        timeout=30,
    )
    logger.info("=== Paperless REQUEST START ===")
    #logger.info("Method: %s", request.method)
    logger.info("URL: %s", str(r.url))
    logger.info("Headers: %s", dict(r.headers))
    #logger.info("Body: %s", body_text)
    logger.info("=== paperless REQUEST END ===")

    r.raise_for_status()
    return r.json()


def get_document_text(document_id: int) -> str:
    doc = get_document(document_id)

    # Paperless liefert den OCR-Inhalt üblicherweise im Feld "content".
    content = doc.get("content")
    if content:
        return content

    raise RuntimeError(f"Dokument {document_id} enthält kein OCR-content-Feld")


@app.post("/webhook")
#TMP for debug

async def webhook(request: Request, x_worker_token: str | None = Header(default=None)):
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")

    if not hmac.compare_digest(x_worker_token or "", WORKER_TOKEN):
      raise HTTPException(status_code=401, detail="unauthorized")

    logger.info("=== WEBHOOK REQUEST START ===")
    logger.info("Method: %s", request.method)
    logger.info("URL: %s", str(request.url))
    logger.info("Headers: %s", dict(request.headers))
    logger.info("Body: %s", body_text)
    logger.info("=== WEBHOOK REQUEST END ===")

    try:
        payload = json.loads(body_text) if body_text else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    document_url = (
        payload.get("document_id")
        or payload.get("id")
        or payload.get("document")
    )
    logger.info("document url: %s", document_url)
    if isinstance(document_url, dict):
        document_url = document_url.get("id")

    document_id = extract_id(document_url)

    if document_id is None:
        raise HTTPException(status_code=400, detail=f"Keine document_id im Payload: {payload}")

    #document_id = int(document_id)

    tmp_dir = OUTPUT_DIR / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    txt_file = tmp_dir / f"paperless_{document_id}.txt"

    try:
        text = get_document_text(document_id)
        txt_file.write_text(text, encoding="utf-8")

        run(["python", "/app/kalenderparser.py", str(txt_file), "--output-dir", str(OUTPUT_DIR)])
        run(["python", "/app/verdienstparser.py", str(txt_file), "--output-dir", str(OUTPUT_DIR)])
        run(["python", "/app/jahresauswertung.py", str(OUTPUT_DIR)])

        for year_dir in OUTPUT_DIR.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            year = year_dir.name
            auswertung = year_dir / f"auswertung_{year}.json"
            report = year_dir / f"report_{year}.html"

            if auswertung.exists():
                run([
                    "python",
                    "/app/html_report.py",
                    str(auswertung),
                    "--output-file",
                    str(report),
                ])

        return {"status": "ok", "document_id": document_id}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
