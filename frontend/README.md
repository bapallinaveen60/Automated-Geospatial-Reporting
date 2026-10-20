# GeoVision web app

React + TypeScript (Vite) front end for non-technical users. It talks to the FastAPI backend in
`src/geovision/api/`.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to the API on :8000
npm run build    # dist/, served by the API at http://localhost:8000
npm run lint
```

Screens: `pages/Reports.tsx` (project list), `pages/NewReport.tsx` (boundary upload + map
preview + submit) and `pages/ReportDetail.tsx` (progress, findings, maps, PDF download).
