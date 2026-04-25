import os
import subprocess
from pathlib import Path

import requests
from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

PAPERLESS_URL = os.environ["PAPERLESS_URL"].rstrip("/")
PAPERLESS_TOKEN = os.environ["PAPERLESS_TOKEN"]
WORKER_TOKEN = os.environ["WORKER_TOKEN"]
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data"))

HEADERS = {"Authorization": f"Token {PAPERLESS_TOKEN}"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def get_document(document_id: int) -> dict:
    r = requests.get(
        f"{PAPERLESS_URL}/api/documents/{document_id}/",
        headers=HEADERS,
        timeout=30,
    )
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
async def webhook(request: Request, x_worker_token: str | None = Header(default=None)):
    if x_worker_token != WORKER_TOKEN:
        raise HTTPException(status_code=401, detail="unauthorized")

    payload = await request.json()

    document_id = (
        payload.get("document_id")
        or payload.get("id")
        or payload.get("document")
    )

    if isinstance(document_id, dict):
        document_id = document_id.get("id")

    if document_id is None:
        raise HTTPException(status_code=400, detail=f"Keine document_id im Payload: {payload}")

    document_id = int(document_id)

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
