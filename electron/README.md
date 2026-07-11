# Smart Job Assistant — Desktop App (Electron)

The desktop app wraps the existing FastAPI backend and React frontend into a
single installable application. At runtime the Electron main process:

1. Starts the bundled backend binary (`sja-backend`, built with PyInstaller) on
   a free port (preferring 8001).
2. Waits for `GET /api/health` to return 200.
3. Opens a window at `http://127.0.0.1:<port>` — the backend serves the built
   React frontend directly, so API calls and WebSockets need no extra wiring.

All user data (SQLite DB, logs, uploaded CVs, Chrome profile) lives in the
per-user data directory, e.g. on macOS:
`~/Library/Application Support/Smart Job Assistant/backend-data/`

Backend logs: `~/Library/Logs/Smart Job Assistant/backend.log`

## Build an installer

From the project root:

```bash
./build_desktop.sh
```

This builds the frontend (`frontend/dist`), the backend binary
(`backend/dist/sja-backend`, with the frontend bundled inside), and packages
everything with electron-builder. Installers land in `electron/release/`
(DMG + ZIP on macOS).

The app is not code-signed. On another Mac, first launch requires
right-click → Open (Gatekeeper).

Note: installers are platform-specific — run the build on Windows to get an
`.exe` (NSIS) and on Linux for an AppImage.

## Development

Run the Electron shell against the source backend (uses `backend/venv`):

```bash
cd frontend && npm run build        # backend serves frontend/dist in dev too
cd ../electron && npm install && npm start
```

To iterate on the frontend with hot reload, run `./run.sh` as before and use
the browser, or point Electron at Vite:

```bash
ELECTRON_START_URL=http://localhost:5173 npm start
```

## Runtime requirements

Google Chrome must be installed on the user's machine — the automation uses
Selenium, and webdriver-manager downloads a matching chromedriver on first run.
