# verdienstparser.py

from pathlib import Path
from datetime import datetime
import argparse
import json
import re


LOGFILE = Path("verdienstparser.log")

BLOCK_RE = re.compile(
    r"Berechnung Auslieferprämie Leistungsmonat\s+(\d{2})/(\d{4})(?:\s+\((Korrektur)\))?",
    re.IGNORECASE,
)

Q_ROW_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*€?\s*$")
SUMME_RE = re.compile(r"^Summe:\s+(.+?)\s*€?\s*$")
BEREITS_RE = re.compile(r"^Bereits abgerechnet:\s+(.+?)\s*€?\s*$")
KORREKTUR_RE = re.compile(r"^Korrektur:\s+(.+?)\s*€?\s*$")


def log(level: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [{level}] {message}"
    print(line)

    with LOGFILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def parse_number(value: str):
    value = value.strip()
    value = value.replace("€", "").replace("%", "").strip()

    if value == "-":
        return None

    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif value.count(".") > 1:
        parts = value.split(".")
        value = "".join(parts[:-1]) + "." + parts[-1]

    return float(value)


def parse_q_row(line: str) -> dict | None:
    line = line.strip()

    if not re.match(r"^\d+\s+", line):
        return None

    tokens = line.replace("€", "").split()

    if len(tokens) < 10:
        raise ValueError(f"Q-Zeile hat zu wenige Spalten: {line}")

    return {
        "q_stufe": int(tokens[0]),
        "anzahl_lieferungen": int(tokens[1]),
        "arbeitswert": parse_number(tokens[2]),
        "verguetung_pro_aw": parse_number(tokens[3]),
        "verguetung_nicht_gewichtet": parse_number(tokens[4]),
        "anzahl_reklamationen": int(tokens[5]),
        "reklaquote_persoenlich_prozent": parse_number(tokens[6]),
        "reklaquote_durchschnitt_prozent": parse_number(tokens[7]),
        "gewichtung": parse_number(tokens[8]),
        "verguetung_gewichtet": parse_number(tokens[9]),
    }


def empty_month(month: int, year: int) -> dict:
    return {
        "leistungsmonat": f"{month:02d}/{year}",
        "jahr": year,
        "monat": month,
        "qualitaetsstufen": [],
        "summe": None,
        "korrekturen": [],
        "kennzahlen": {},
    }


def file_for_month(output_dir: Path, month: int, year: int) -> Path:
    year_dir = output_dir / str(year)
    return year_dir / f"verdienst_{month:02d}-{year}.json"


def load_or_create_month(output_dir: Path, month: int, year: int) -> dict:
    path = file_for_month(output_dir, month, year)

    if path.exists():
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    return empty_month(month, year)


def write_month_json(data: dict, output_dir: Path) -> Path:
    year = data["jahr"]
    month = data["monat"]

    year_dir = output_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    path = file_for_month(output_dir, month, year)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    return path


def recalc_kennzahlen(data: dict) -> None:
    arbeitswert_summe = sum(row["arbeitswert"] for row in data["qualitaetsstufen"])
    verguetung_summe = sum(row["verguetung_gewichtet"] for row in data["qualitaetsstufen"])

    minutenpreis = None
    if arbeitswert_summe:
        minutenpreis = verguetung_summe / arbeitswert_summe

    data["kennzahlen"] = {
        "arbeitswert_summe": arbeitswert_summe,
        "verguetung_gewichtet_summe": verguetung_summe,
        "gewichteter_minutenpreis": minutenpreis,
    }


def extract_blocks(text: str) -> list[dict]:
    matches = list(BLOCK_RE.finditer(text))
    blocks = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        month = int(match.group(1))
        year = int(match.group(2))
        is_korrektur = bool(match.group(3))

        blocks.append(
            {
                "month": month,
                "year": year,
                "is_korrektur": is_korrektur,
                "text": text[start:end],
            }
        )

    return blocks


def parse_block(block: dict) -> dict:
    rows = []
    summe = None
    bereits_abgerechnet = None
    korrektur = None

    block_text = re.split(
        r"\n\s*(Zusammenfassung|Anlage:)",
        block["text"],
        maxsplit=1,
    )[0]

    for raw_line in block_text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        q_row = parse_q_row(line)
        if q_row:
            rows.append(q_row)
            continue

        m = SUMME_RE.match(line)
        if m:
            summe = parse_number(m.group(1))
            continue

        m = BEREITS_RE.match(line)
        if m:
            bereits_abgerechnet = parse_number(m.group(1))
            continue

        m = KORREKTUR_RE.match(line)
        if m:
            korrektur = parse_number(m.group(1))
            continue

    return {
        "leistungsmonat": f"{block['month']:02d}/{block['year']}",
        "jahr": block["year"],
        "monat": block["month"],
        "ist_korrektur": block["is_korrektur"],
        "qualitaetsstufen": rows,
        "summe": summe,
        "bereits_abgerechnet": bereits_abgerechnet,
        "korrektur": korrektur,
    }


def apply_regular_block(parsed_block: dict, output_dir: Path) -> Path:
    data = empty_month(parsed_block["monat"], parsed_block["jahr"])
    data["qualitaetsstufen"] = parsed_block["qualitaetsstufen"]
    data["summe"] = parsed_block["summe"]

    recalc_kennzahlen(data)

    output_file = write_month_json(data, output_dir)
    log("INFO", f"{parsed_block['leistungsmonat']} geschrieben -> {output_file}")
    return output_file


def apply_correction_block(parsed_block: dict, output_dir: Path) -> Path | None:
    month = parsed_block["monat"]
    year = parsed_block["jahr"]
    path = file_for_month(output_dir, month, year)

    korrekturwert = parsed_block["korrektur"]

    # 0,00 ist Normalfall → still ignorieren
    if korrekturwert is None or abs(korrekturwert) < 0.000001:
        return None

    if not path.exists():
        log(
            "WARN",
            f"Korrektur für {month:02d}/{year} = {korrekturwert:.2f}, aber Monatsdatei existiert nicht: {path}",
        )
        return None

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    data["qualitaetsstufen"] = parsed_block["qualitaetsstufen"]
    data["summe"] = parsed_block["summe"]

    data["korrektur_angewendet"] = True
    data["korrekturwert"] = korrekturwert

    recalc_kennzahlen(data)

    output_file = write_month_json(data, output_dir)

    log(
        "INFO",
        f"Korrektur angewendet für {month:02d}/{year} = {korrekturwert:.2f} -> {output_file}",
    )

    return output_file


def parse_file(input_file: Path, output_dir: Path) -> list[Path]:
    try:
        text = input_file.read_text(encoding="utf-8")
    except Exception as exc:
        log("ERROR", f"{input_file} konnte nicht gelesen werden: {exc}")
        return []

    blocks = extract_blocks(text)

    if not blocks:
        log("WARN", f"{input_file}: keine Auslieferprämien-Blöcke gefunden")
        return []

    written = []

    for block in blocks:
        try:
            parsed_block = parse_block(block)

            if parsed_block["ist_korrektur"]:
                result = apply_correction_block(parsed_block, output_dir)
            else:
                result = apply_regular_block(parsed_block, output_dir)

            if result:
                written.append(result)

        except Exception as exc:
            log(
                "ERROR",
                f"{input_file}: Block {block['month']:02d}/{block['year']} fehlgeschlagen: {exc}",
            )

    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parst Auslieferprämien-Blöcke aus OCR-TXT-Dateien."
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))

    args = parser.parse_args()

    written = parse_file(args.input_file, args.output_dir)

    if written:
        log("INFO", f"OK: {args.input_file}")
    else:
        log("WARN", f"Keine Datei geschrieben: {args.input_file}")


if __name__ == "__main__":
    main()
