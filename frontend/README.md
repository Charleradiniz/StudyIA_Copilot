# Frontend Workspace

This package contains the React/Vite client for StudyIA Copilot.

Key responsibilities:
- authenticate users through backend-managed HttpOnly cookies
- render the shared document library and chat history
- keep desktop and mobile sessions in sync with the backend
- open grounded PDF sources in the viewer with highlighted evidence

Useful commands:

```bash
npm run dev
npm run lint
npm run test
npm run test:e2e
```

Environment:

```env
VITE_API_URL=http://127.0.0.1:8000
```
