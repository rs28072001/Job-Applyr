import { useEffect } from "react";
import { WS_URL } from "../api/client";
import type { WSEvent } from "../api/types";
import { useSessionStore } from "../store/sessionStore";

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

/**
 * Module-level singleton connection. The hook can mount any number of times
 * (StrictMode double-mount, multiple components, HMR) without ever opening a
 * second socket — which previously caused every event to be processed 2-3×,
 * showing duplicate job rows and log lines.
 */
let socket: WebSocket | null = null;
let attempts = 0;
let refCount = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return; // already connected/connecting — never duplicate
  }

  const ws = new WebSocket(WS_URL);
  socket = ws;

  ws.onopen = () => { attempts = 0; };

  ws.onmessage = (e) => {
    try {
      const event: WSEvent = JSON.parse(e.data);
      // Call the store directly so a single connection feeds all subscribers.
      useSessionStore.getState().handleEvent(event);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = () => {
    socket = null;
    // Only reconnect while at least one component still wants the feed.
    if (refCount > 0) {
      const delay = RECONNECT_DELAYS[Math.min(attempts, RECONNECT_DELAYS.length - 1)];
      attempts += 1;
      reconnectTimer = setTimeout(connect, delay);
    }
  };

  ws.onerror = () => ws.close();
}

export function useWebSocket() {
  useEffect(() => {
    refCount += 1;
    connect();
    return () => {
      refCount -= 1;
      // Tear down only when the last consumer unmounts.
      if (refCount <= 0) {
        refCount = 0;
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        socket?.close();
        socket = null;
      }
    };
  }, []);
}
