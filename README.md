# Derivados MX

Plataforma académica de análisis de derivados sobre emisoras con contratos en MexDer.
Los datos (precios, estados financieros, dividendos y consenso de Yahoo Finance) se actualizan solos
cada día hábil a las 16:30 (hora de Ciudad de México) con GitHub Actions y se publican en GitHub Pages.

- `docs/index.html` — la app (un solo archivo).
- `docs/data/live.json` — datos del día (los genera la tarea programada).
- `scripts/actualizar.py` — descarga de Yahoo Finance.
- `.github/workflows/actualizar.yml` — tarea programada y publicación.

Herramienta académica. No constituye asesoría de inversión.
