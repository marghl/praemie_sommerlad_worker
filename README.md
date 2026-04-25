# Prämienauswertung Worker (Paperless-ngx)

Lokaler Worker zur automatischen Auswertung von Provisions-/Spesenabrechnungen aus Paperless-ngx.
Funktioniert nur mit den neuen (post Potiska) Abrechnungen der Sommerlag Logistik

## Funktionen

- Verarbeitung von OCR-Texten aus Paperless
- Extraktion von:
  - Einsatzkalender (Arbeitstage, Sollminuten)
  - Qualitätsstufen / Prämien
- Berechnung:
  - Soll vs. Ist Minuten
  - Durchschnittlicher Minutenpreis
  - Differenz in Minuten und €
- Ausgabe:
  - JSON (maschinenlesbar)
  - HTML (übersichtlicher Report)
- Unterstützung von Korrekturen (überschreiben nur relevante Felder)

---

## Architektur

```text
Paperless Workflow
  → Dokumenttyp: Spesen/Provision
  → Webhook → Worker

Worker (Docker)
  → holt OCR-Text via API
  → startet Parser-Pipeline
  → schreibt JSON + HTML
