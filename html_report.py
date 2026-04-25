# html_report.py

from pathlib import Path
import argparse
import html
import json


def fmt_num(value, digits=2):
    if value is None:
        return "–"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(value):
    if value is None:
        return "–"
    return f"{int(value):,}".replace(",", ".")


def status_class(monat):
    if monat["status"] != "ok":
        return "missing"
    if monat["differenz_minuten"] is not None and monat["differenz_minuten"] < 0:
        return "negative"
    return "ok"


def make_html(data):
    jahr = data["jahr"]
    z = data["zusammenfassung"]

    rows = []

    for m in data["monate"]:
        hinweise = ", ".join(m.get("hinweise", []))
        cls = status_class(m)

        rows.append(f"""
        <tr class="{cls}">
          <td>{m["monat"]:02d}/{jahr}</td>
          <td>{html.escape(m["status"])}</td>
          <td class="num">{fmt_int(m["arbeitstage"])}</td>
          <td class="num">{fmt_int(m["soll_minuten"])}</td>
          <td class="num">{fmt_int(m["minuten_laut_abrechnung"])}</td>
          <td class="num">{fmt_int(m["differenz_minuten"])}</td>
          <td class="num">{fmt_num(m["durchschnittlicher_minutenpreis"], 4)}</td>
          <td class="num">{fmt_num(m["praemie"], 2)} €</td>
          <td class="num">{fmt_num(m["differenz_euro"], 2)} €</td>
          <td>{html.escape(hinweise)}</td>
        </tr>
        """)

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>Jahresauswertung {jahr}</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 2rem;
      background: #f6f7f9;
      color: #1f2937;
    }}

    h1 {{
      margin-bottom: 0.25rem;
    }}

    .subtitle {{
      color: #6b7280;
      margin-bottom: 2rem;
    }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}

    .card {{
      background: white;
      border-radius: 12px;
      padding: 1rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}

    .card .label {{
      color: #6b7280;
      font-size: 0.85rem;
      margin-bottom: 0.4rem;
    }}

    .card .value {{
      font-size: 1.4rem;
      font-weight: 700;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: white;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}

    th, td {{
      padding: 0.7rem 0.8rem;
      border-bottom: 1px solid #e5e7eb;
      font-size: 0.92rem;
    }}

    th {{
      background: #111827;
      color: white;
      text-align: left;
      position: sticky;
      top: 0;
    }}

    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}

    tr.ok {{
      background: white;
    }}

    tr.negative {{
      background: #fff7ed;
    }}

    tr.missing {{
      background: #fee2e2;
    }}

    tfoot td {{
      font-weight: 700;
      background: #f3f4f6;
    }}

    .legend {{
      margin-top: 1rem;
      color: #6b7280;
      font-size: 0.9rem;
    }}
  </style>
</head>
<body>

  <h1>Jahresauswertung {jahr}</h1>
  <div class="subtitle">Soll/Ist-Auswertung aus Kalender- und Verdienstdaten</div>

  <section class="cards">
    <div class="card">
      <div class="label">Vollständige Monate</div>
      <div class="value">{z["vollstaendige_monate"]}</div>
    </div>
    <div class="card">
      <div class="label">Arbeitstage</div>
      <div class="value">{fmt_int(z["arbeitstage"])}</div>
    </div>
    <div class="card">
      <div class="label">Soll-Minuten</div>
      <div class="value">{fmt_int(z["soll_minuten"])}</div>
    </div>
    <div class="card">
      <div class="label">Ist-Minuten</div>
      <div class="value">{fmt_int(z["minuten_laut_abrechnung"])}</div>
    </div>
    <div class="card">
      <div class="label">Differenz Minuten</div>
      <div class="value">{fmt_int(z["differenz_minuten"])}</div>
    </div>
    <div class="card">
      <div class="label">Prämie</div>
      <div class="value">{fmt_num(z["praemie"], 2)} €</div>
    </div>
    <div class="card">
      <div class="label">Ø Minutenpreis</div>
      <div class="value">{fmt_num(z["durchschnittlicher_minutenpreis"], 4)} €</div>
    </div>
    <div class="card">
      <div class="label">Differenz Euro</div>
      <div class="value">{fmt_num(z["differenz_euro"], 2)} €</div>
    </div>
  </section>

  <table>
    <thead>
      <tr>
        <th>Monat</th>
        <th>Status</th>
        <th>AT</th>
        <th>Soll-Min.</th>
        <th>Ist-Min.</th>
        <th>Δ Min.</th>
        <th>€/Min.</th>
        <th>Prämie</th>
        <th>Δ Euro</th>
        <th>Hinweise</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
    <tfoot>
      <tr>
        <td>Summe</td>
        <td></td>
        <td class="num">{fmt_int(z["arbeitstage"])}</td>
        <td class="num">{fmt_int(z["soll_minuten"])}</td>
        <td class="num">{fmt_int(z["minuten_laut_abrechnung"])}</td>
        <td class="num">{fmt_int(z["differenz_minuten"])}</td>
        <td class="num">{fmt_num(z["durchschnittlicher_minutenpreis"], 4)}</td>
        <td class="num">{fmt_num(z["praemie"], 2)} €</td>
        <td class="num">{fmt_num(z["differenz_euro"], 2)} €</td>
        <td></td>
      </tr>
    </tfoot>
  </table>

  <div class="legend">
    Rot = fehlende/unvollständige Daten · Orange = negative Monatsdifferenz
  </div>

</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Erzeugt HTML-Report aus auswertung_YYYY.json")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--output-file", type=Path)

    args = parser.parse_args()

    with args.input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    output_file = args.output_file
    if output_file is None:
        output_file = args.input_file.with_suffix(".html")

    output_file.write_text(make_html(data), encoding="utf-8")

    print(f"HTML geschrieben: {output_file}")


if __name__ == "__main__":
    main()
