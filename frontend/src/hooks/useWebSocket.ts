import { useEffect, useRef, useCallback } from "react";
import { WS_URL } from "../api/client";
import type { WSEvent } from "../api/types";
import { useSessionStore } from "../store/sessionStore";

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000];

export function useWebSocket() {
  const wsRef      = useRef<WebSocket | null>(null);
  const attemptsRef= useRef(0);
  const activeRef  = useRef(true);
  const handleEvent= useSessionStore((s) => s.handleEvent);

  const connect = useCallback(() => {
    if (!activeRef.current) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptsRef.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data);
        handleEvent(event);
      } catch {
        // ignore malformed frames
      }
    };

    ws.onclose = () => {
      if (!activeRef.current) return;
      const delay = RECONNECT_DELAYS[Math.min(attemptsRef.current, RECONNECT_DELAYS.length - 1)];
      attemptsRef.current += 1;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [handleEvent]);

  useEffect(() => {
    activeRef.current = true;
    connect();
    return () => {
      activeRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);
}
