# tests/test_verdienstparser.py

from verdienstparser import parse_q_row


def test_q_row_parsing():
    line = "2 2 180 0,060 € 10,80 € 0 0,0% 9,3% 1,50 16,20 €"

    row = parse_q_row(line)

    assert row["q_stufe"] == 2
    assert row["arbeitswert"] == 180
    assert row["verguetung_gewichtet"] == 16.20
