# jahresauswertung.py

from pathlib import Path
from datetime import datetime
import argparse
import json
import os

LOGFILE = Path("jahresauswertung.log")
MINUTEN = int(os.getenv("MINUTEN_PRO_TAG"))

def log(level: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} [{level}] {message}"
    print(line)

    with LOGFILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def kalender_file(year_dir: Path, year: int, month: int) -> Path:
    yy = str(year)[-2:]
    return year_dir / f"kalender_{month:02d}-{yy}.json"


def verdienst_file(year_dir: Path, year: int, month: int) -> Path:
    return year_dir / f"verdienst_{month:02d}-{year}.json"


def safe_sum(values):
    return sum(value for value in values if value is not None)


def berechne_monat(year_dir: Path, year: int, month: int) -> dict:
    k_path = kalender_file(year_dir, year, month)
    v_path = verdienst_file(year_dir, year, month)

    kalender = load_json(k_path)
    verdienst = load_json(v_path)

    result = {
        "monat": month,
        "leistungsmonat": f"{month:02d}/{year}",
        "kalender_datei": str(k_path) if k_path.exists() else None,
        "verdienst_datei": str(v_path) if v_path.exists() else None,
        "status": "ok",
        "hinweise": [],
        "arbeitstage": None,
        "soll_minuten": None,
        "minuten_laut_abrechnung": None,
        "praemie": None,
        "durchschnittlicher_minutenpreis": None,
        "differenz_minuten": None,
        "differenz_euro": None,
    }

    if kalender is None:
        result["status"] = "unvollständig"
        result["hinweise"].append("Kalenderdatei fehlt")

    if verdienst is None:
        result["status"] = "unvollständig"
        result["hinweise"].append("Verdienstdatei fehlt")

    if kalender is None or verdienst is None:
        return result

    tage = kalender.get("tage", [])
    qualitaetsstufen = verdienst.get("qualitaetsstufen", [])

    arbeitstage = sum(1 for tag in tage if tag.get("arbeitstag") is True)
    soll_minuten = arbeitstage * MINUTEN

    minuten_laut_abrechnung = safe_sum(
        row.get("arbeitswert") for row in qualitaetsstufen
    )

    praemie = verdienst.get("summe")

    if praemie is None:
        praemie = safe_sum(
            row.get("verguetung_gewichtet") for row in qualitaetsstufen
        )

    if minuten_laut_abrechnung:
        minutenpreis = praemie / minuten_laut_abrechnung
    else:
        minutenpreis = None

    differenz_minuten = minuten_laut_abrechnung - soll_minuten

    if minutenpreis is not None:
        differenz_euro = differenz_minuten * minutenpreis
    else:
        differenz_euro = None

    result.update(
        {
            "arbeitstage": arbeitstage,
            "soll_minuten": soll_minuten,
            "minuten_laut_abrechnung": minuten_laut_abrechnung,
            "praemie": round(praemie, 2) if praemie is not None else None,
            "durchschnittlicher_minutenpreis": minutenpreis,
            "differenz_minuten": differenz_minuten,
            "differenz_euro": round(differenz_euro, 2)
            if differenz_euro is not None
            else None,
        }
    )

    if verdienst.get("korrektur_angewendet"):
        result["hinweise"].append(
            f"Korrektur angewendet: {verdienst.get('korrekturwert')}"
        )

    return result


def berechne_jahr(year_dir: Path) -> dict:
    year = int(year_dir.name)

    monate = [
        berechne_monat(year_dir, year, month)
        for month in range(1, 13)
    ]

    gueltige_monate = [m for m in monate if m["status"] == "ok"]

    sum_arbeitstage = safe_sum(m["arbeitstage"] for m in gueltige_monate)
    sum_soll = safe_sum(m["soll_minuten"] for m in gueltige_monate)
    sum_ist = safe_sum(m["minuten_laut_abrechnung"] for m in gueltige_monate)
    sum_praemie = safe_sum(m["praemie"] for m in gueltige_monate)

    if sum_ist:
        jahres_minutenpreis = sum_praemie / sum_ist
    else:
        jahres_minutenpreis = None

    differenz_minuten = sum_ist - sum_soll

    if jahres_minutenpreis is not None:
        differenz_euro = differenz_minuten * jahres_minutenpreis
    else:
        differenz_euro = None

    return {
        "jahr": year,
        "monate": monate,
        "zusammenfassung": {
            "vollstaendige_monate": len(gueltige_monate),
            "fehlende_oder_unvollstaendige_monate": 12 - len(gueltige_monate),
            "arbeitstage": sum_arbeitstage,
            "soll_minuten": sum_soll,
            "minuten_laut_abrechnung": sum_ist,
            "praemie": round(sum_praemie, 2),
            "durchschnittlicher_minutenpreis": jahres_minutenpreis,
            "differenz_minuten": differenz_minuten,
            "differenz_euro": round(differenz_euro, 2)
            if differenz_euro is not None
            else None,
        },
    }


def write_auswertung(year_dir: Path, auswertung: dict) -> Path:
    year = auswertung["jahr"]
    output_file = year_dir / f"auswertung_{year}.json"

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(auswertung, file, ensure_ascii=False, indent=2)

    return output_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Erzeugt Jahresauswertungen aus Kalender- und Verdienst-JSON-Dateien."
    )
    parser.add_argument(
        "data_dir",
        type=Path,
        help="Basisordner, der Jahresordner enthält, z. B. data",
    )

    args = parser.parse_args()

    if not args.data_dir.exists():
        raise SystemExit(f"Ordner existiert nicht: {args.data_dir}")

    year_dirs = sorted(
        path for path in args.data_dir.iterdir()
        if path.is_dir() and path.name.isdigit()
    )

    if not year_dirs:
        raise SystemExit(f"Keine Jahresordner gefunden in: {args.data_dir}")

    for year_dir in year_dirs:
        try:
            auswertung = berechne_jahr(year_dir)
            output_file = write_auswertung(year_dir, auswertung)
            log("INFO", f"{year_dir.name}: Auswertung geschrieben -> {output_file}")
        except Exception as exc:
            log("ERROR", f"{year_dir}: Auswertung fehlgeschlagen: {exc}")


if __name__ == "__main__":
    main()
