# tests/test_kalenderparser.py

from kalenderparser import parse_kalender


def test_arbeitstag_erkennung():
    text = """
Einsatz im Leistungsmonat 06/2025
01 Mo - 15,00 - -
02 Di Urlaub - - - -
03 Mi Bezahlter - - 68,84 -
Feiertag
Summe 0 0 0 0
"""

    result = parse_kalender(text)
    tage = result["tage"]

    assert tage[0]["arbeitstag"] is True
    assert tage[1]["arbeitstag"] is False
    assert tage[2]["sonderfall"] in ["bezahlter_feiertag", "bezahlter_feiertag_unsicher"]
