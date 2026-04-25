# tests/test_jahresauswertung.py

from jahresauswertung import berechne_monat


def test_soll_berechnung(tmp_path):
    year_dir = tmp_path / "2025"
    year_dir.mkdir()

    kalender = {
        "tage": [
            {"arbeitstag": True},
            {"arbeitstag": True},
            {"arbeitstag": False},
        ]
    }

    verdienst = {
        "qualitaetsstufen": [
            {"arbeitswert": 840, "verguetung_gewichtet": 100}
        ],
        "summe": 100
    }

    (year_dir / "kalender_01-25.json").write_text(
        __import__("json").dumps(kalender)
    )
    (year_dir / "verdienst_01-2025.json").write_text(
        __import__("json").dumps(verdienst)
    )

    result = berechne_monat(year_dir, 2025, 1)

    assert result["soll_minuten"] == 2 * 420
    assert result["minuten_laut_abrechnung"] == 840
