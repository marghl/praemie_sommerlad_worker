# Prämienauswertung Worker (Paperless-ngx)

Lokaler Worker zur automatischen Auswertung von Provisions-/Spesenabrechnungen aus Paperless-ngx.
Funktioniert nur mit den neuen (post Potiska) Abrechnungen der Sommerlad Logistik. 
Das Docker Release macht eigentlich keinen Sinn. Für mein NAS ist es einfacher und Spaß hab ich auch dran ;)


## Architektur

```text
Paperless Workflow
  → Dokumenttyp: Spesen/Provision
  → Webhook → Worker

Worker (Docker)
  → holt OCR-Text via API
  → startet Parser-Pipeline
  → schreibt JSON + HTML
