const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const net = require("net");
const path = require("path");
const fs = require("fs");

let backendProcess = null;
let mainWindow = null;
let quitting = false;

const isDev = !app.isPackaged;
const DEFAULT_PORT = 8001;

/** Find a free port, preferring the default so dev tooling stays predictable. */
function findFreePort(preferred) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => {
      // preferred port busy — let the OS pick one
      const fallback = net.createServer();
      fallback.listen(0, "127.0.0.1", () => {
        const port = fallback.address().port;
        fallback.close(() => resolve(port));
      });
    });
    server.listen(preferred, "127.0.0.1", () => {
      server.close(() => resolve(preferred));
    });
  });
}

function backendCommand(port) {
  const userDataDir = path.join(app.getPath("userData"), "backend-data");
  const env = {
    ...process.env,
    SJA_BASE_DIR: userDataDir,
    SJA_PORT: String(port),
  };

  if (isDev) {
    // Dev: run uvicorn from the project venv against the source tree.
    const backendDir = path.resolve(__dirname, "..", "backend");
    const python = path.join(backendDir, "venv", "bin", "python");
    return {
      cmd: python,
      args: ["-m", "uvicorn", "api.server:app", "--host", "127.0.0.1", "--port", String(port)],
      opts: { cwd: backendDir, env },
    };
  }

  // Packaged: PyInstaller onedir bundle shipped in extraResources.
  const exeName = process.platform === "win32" ? "sja-backend.exe" : "sja-backend";
  const exe = path.join(process.resourcesPath, "sja-backend", exeName);
  return { cmd: exe, args: [], opts: { env } };
}

function startBackend(port) {
  const { cmd, args, opts } = backendCommand(port);

  if (!isDev && !fs.existsSync(cmd)) {
    dialog.showErrorBox(
      "Smart Job Assistant",
      `Backend binary not found:\n${cmd}\n\nThe application package is incomplete.`
    );
    app.quit();
    return;
  }

  const logDir = app.getPath("logs");
  fs.mkdirSync(logDir, { recursive: true });
  const logStream = fs.createWriteStream(path.join(logDir, "backend.log"), { flags: "a" });

  backendProcess = spawn(cmd, args, { ...opts, stdio: ["ignore", "pipe", "pipe"] });
  backendProcess.stdout.pipe(logStream);
  backendProcess.stderr.pipe(logStream);

  backendProcess.on("exit", (code) => {
    backendProcess = null;
    if (!quitting && code !== 0 && code !== null) {
      dialog.showErrorBox(
        "Smart Job Assistant",
        `The backend stopped unexpectedly (exit code ${code}).\nSee logs at: ${path.join(logDir, "backend.log")}`
      );
      app.quit();
    }
  });
}

function waitForHealth(port, timeoutMs = 60000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = () => {
      const req = http.get(
        { host: "127.0.0.1", port, path: "/api/health", timeout: 2000 },
        (res) => {
          res.resume();
          if (res.statusCode === 200) return resolve();
          retry();
        }
      );
      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        return reject(new Error("Backend did not become healthy in time"));
      }
      setTimeout(poll, 500);
    };
    poll();
  });
}

function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: "Smart Job Assistant",
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow.show());

  // External links open in the system browser, not inside the app window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(`http://127.0.0.1:${port}`) && !url.startsWith(`http://localhost:${port}`)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  const startUrl = process.env.ELECTRON_START_URL || `http://127.0.0.1:${port}`;
  mainWindow.loadURL(startUrl);

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function stopBackend() {
  if (backendProcess) {
    try {
      backendProcess.kill("SIGTERM");
    } catch {
      /* already dead */
    }
    backendProcess = null;
  }
}

// Single instance — a second launch focuses the existing window.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    const port = await findFreePort(DEFAULT_PORT);
    startBackend(port);
    try {
      await waitForHealth(port);
    } catch (err) {
      dialog.showErrorBox(
        "Smart Job Assistant",
        `Could not start the backend server.\n${err.message}\nSee logs at: ${path.join(app.getPath("logs"), "backend.log")}`
      );
      app.quit();
      return;
    }
    createWindow(port);

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow(port);
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });

  app.on("before-quit", () => {
    quitting = true;
    stopBackend();
  });

  process.on("exit", stopBackend);
}
