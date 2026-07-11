// Minimal preload — the renderer is the existing web frontend and talks to the
// backend over HTTP/WebSocket, so no Node APIs need to be exposed. Kept as an
// explicit (empty) bridge so future desktop-only features have a home.
const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("sjaDesktop", {
  isDesktop: true,
});
