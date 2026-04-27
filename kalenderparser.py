# kalenderparser.py

from pathlib import Path
from datetime import date, datetime
import argparse
import json
import re
import os

LOGFILE = Path("kalenderparser.log")
MONTH_RE = re.compile(r"Einsatz im Leistungsmonat\s+(\d{2})/(\d{4})")
DAY_RE = re.compile(r"^(0[1-9]|[12][0-9]|3[01])\s+(Mo|Di|Mi|Do|Fr|Sa|So)\s+(.*)$")
SUMME_RE = re.compile(r"^Summe\s+(.+)$")
MINUTEN = int(os.getenv("MINUTEN_PRO-TAG"))

def log(level: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [{level}] {message}"
    print(line)

    with LOGFILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def parse_number(value: str):
    value = value.strip()

    if value == "-":
        return None

    # Deutsch: 1.087,35 -> 1087.35
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    else:
        # OCR-Fall: 1.087.35 -> 1087.35
        if value.count(".") > 1:
            parts = value.split(".")
            value = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Ungültiger Zahlenwert: {value}")


def is_amount_token(token: str) -> bool:
    token = token.strip()

    if token == "-":
        return True

    return bool(re.match(r"^-?\d+(?:[,.]\d+)*$", token))


def split_day_entries(line: str) -> list[str]:
    matches = list(
        re.finditer(
            r"\b(0[1-9]|[12][0-9]|3[01])\s+(Mo|Di|Mi|Do|Fr|Sa|So)\b",
            line,
        )
    )

    entries = []

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        entries.append(line[start:end].strip())

    return entries


def parse_day_entry(entry: str, month: int, year: int) -> dict:
    match = DAY_RE.match(entry)

    if not match:
        raise ValueError(f"Ungültiger Tagesblock: {entry}")

    day = int(match.group(1))
    weekday = match.group(2)
    rest = match.group(3).strip()

    tokens = rest.split()

    amount_positions = []

    for idx in range(len(tokens) - 1, -1, -1):
        if is_amount_token(tokens[idx]):
            amount_positions.append(idx)

        if len(amount_positions) == 4:
            break

    if len(amount_positions) != 4:
        raise ValueError(f"Konnte keine 4 Vergütungsfelder finden: {entry}")

    amount_positions = sorted(amount_positions)
    amount_tokens = [tokens[i] for i in amount_positions]

    inkasso, fahrer, ausgleich, spesen = map(parse_number, amount_tokens)

    bemerkung_tokens = [
        token
        for idx, token in enumerate(tokens)
        if idx not in amount_positions
    ]

    bemerkung = " ".join(bemerkung_tokens) if bemerkung_tokens else None

    tag = {
        "datum": date(year, month, day).isoformat(),
        "tag": weekday,
        "bemerkung": bemerkung,
        "inkasso": inkasso,
        "fahrer": fahrer,
        "ausgleich": ausgleich,
        "spesen": spesen,
    }

    return klassifiziere_tag(tag)


def klassifiziere_tag(tag: dict) -> dict:
    bemerkung = (tag.get("bemerkung") or "").lower()

    hat_arbeitseintrag = any(
        [
            tag.get("inkasso") is not None,
            tag.get("fahrer") is not None,
        ]
    )

    tag["arbeitstag"] = hat_arbeitseintrag

    if "urlaub" in bemerkung:
        tag["sonderfall"] = "urlaub"
    elif "krank" in bemerkung:
        tag["sonderfall"] = "krank"
    elif "freizeitausgleich" in bemerkung:
        tag["sonderfall"] = "freizeitausgleich"
    elif "dienstreise" in bemerkung:
        tag["sonderfall"] = "dienstreise"
    elif "feiertag" in bemerkung and "bezahlt" in bemerkung:
        tag["sonderfall"] = "bezahlter_feiertag"
    elif "bezahlter" in bemerkung:
        tag["sonderfall"] = "bezahlter_feiertag_unsicher"
    elif "feiertag" in bemerkung:
        tag["sonderfall"] = "feiertag"
    elif bemerkung:
        tag["sonderfall"] = "sonstiges"
    else:
        tag["sonderfall"] = None

    return tag


def extract_kalender_section(text: str) -> tuple[int, int, list[str]]:
    month_match = MONTH_RE.search(text)

    if not month_match:
        raise ValueError("Kein Abschnitt 'Einsatz im Leistungsmonat MM/YYYY' gefunden.")

    month = int(month_match.group(1))
    year = int(month_match.group(2))

    start = month_match.start()
    remaining_text = text[start:]

    end_match = re.search(r"\n\s*Berechnung Auslieferprämie", remaining_text)

    if end_match:
        section = remaining_text[: end_match.start()]
    else:
        section = remaining_text

    lines = [line.strip() for line in section.splitlines() if line.strip()]

    return month, year, lines


def is_header_line(line: str) -> bool:
    return line.startswith(
        (
            "Einsatz im Leistungsmonat",
            "Tag ",
            "Inkasso",
            "o.Beif.",
        )
    )


def parse_kalender(text: str) -> dict:
    month, year, lines = extract_kalender_section(text)

    tage = []
    summe = None

    i = 0

    while i < len(lines):
        line = lines[i]

        if DAY_RE.match(line):
            combined = line

            while i + 1 < len(lines):
                next_line = lines[i + 1]

                if DAY_RE.match(next_line):
                    break

                if SUMME_RE.match(next_line):
                    break

                if is_header_line(next_line):
                    break

                combined += " " + next_line
                i += 1

            for entry in split_day_entries(combined):
                tage.append(parse_day_entry(entry, month, year))

        elif SUMME_RE.match(line):
            values = SUMME_RE.match(line).group(1).split()

            if len(values) != 4:
                raise ValueError(f"Summe-Zeile hat nicht 4 Werte: {line}")

            summe = {
                "inkasso": parse_number(values[0]),
                "fahrer": parse_number(values[1]),
                "ausgleich": parse_number(values[2]),
                "spesen": parse_number(values[3]),
            }

        i += 1

    tage = sorted(tage, key=lambda item: item["datum"])

    return {
        "leistungsmonat": f"{month:02d}/{year}",
        "jahr": year,
        "monat": month,
        "tage": tage,
        "summe": summe,
        "kennzahlen": {
            "arbeitstage": sum(1 for tag in tage if tag["arbeitstag"]),
            "soll_minuten": sum(MINUTEN for tag in tage if tag["arbeitstag"]),
            "sonderfaelle": sum(1 for tag in tage if tag["sonderfall"] is not None),
        },
    }


def write_month_json(parsed: dict, output_dir: Path) -> Path:
    year = parsed["jahr"]
    month = parsed["monat"]
    yy = str(year)[-2:]

    year_dir = output_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    output_file = year_dir / f"kalender_{month:02d}-{yy}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(parsed, file, ensure_ascii=False, indent=2)

    return output_file


def parse_file(input_file: Path, output_dir: Path) -> Path | None:
    try:
        text = input_file.read_text(encoding="utf-8")
    except Exception as exc:
        log("ERROR", f"{input_file} konnte nicht gelesen werden: {exc}")
        return None

    try:
        parsed = parse_kalender(text)
    except Exception as exc:
        log("ERROR", f"{input_file} parsing fehlgeschlagen: {exc}")
        return None

    try:
        output_file = write_month_json(parsed, output_dir)
        log("INFO", f"{input_file} -> {output_file}")
        return output_file
    except Exception as exc:
        log("ERROR", f"{input_file} schreiben fehlgeschlagen: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parst den Einsatzkalender aus OCR-TXT-Dateien."
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))

    args = parser.parse_args()

    result = parse_file(args.input_file, args.output_dir)

    if result is None:
        log("ERROR", "FAILED")
        raise SystemExit(1)

    log("INFO", "OK")


if __name__ == "__main__":
    main()
