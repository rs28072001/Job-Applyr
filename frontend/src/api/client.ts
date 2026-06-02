import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "",  // empty = same origin (proxied in dev, nginx in Docker)
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

export const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws`;
