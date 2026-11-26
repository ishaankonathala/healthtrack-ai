# HealthTrack AI web frontend

## Run locally

Start FastAPI in one terminal:

```bash
.venv/bin/uvicorn backend.app.main:app --reload
```

Start the React app in another:

```bash
cd frontend/web
npm install
npm run dev
```

Vite proxies `/api-root` (rewritten to `/`), `/health`, `/symptoms`, `/analytics`, `/ai`, and `/rag` to `http://127.0.0.1:8000` during development. To use a different API origin, set `VITE_API_BASE_URL` in the frontend environment; the value is public configuration, not a secret. In production, route these API paths through the frontend’s origin. A separate backend origin also needs CORS permission; the existing FastAPI app does not configure CORS.

## Patient selection

The patient selector starts empty. `patient-001` is offered as the documented example from the root README; it is not seeded data, so the API may return an empty history. You can enter another existing synthetic patient ID. Use synthetic records only; this prototype has no authentication or patient-level authorization.

AI summary requests are sent only when **Generate summary** is clicked. Health education questions are sent only when **Ask question** is submitted.
