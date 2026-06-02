"""WebSocket /ws — streams tracker events to the browser in real time."""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import api.event_queue as eq

logger  = logging.getLogger(__name__)
router  = APIRouter()

# Track all active connections so we can broadcast to multiple browser tabs
_connections: list[WebSocket] = []


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.append(websocket)
    logger.info("WebSocket connected (%d total)", len(_connections))

    try:
        while True:
            # Wait up to 1s for the next event; send a heartbeat if nothing arrives
            event = await eq.get_event_timeout(timeout=1.0)
            if event is None:
                # Heartbeat keeps the connection alive through proxies/load-balancers
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
            else:
                try:
                    await websocket.send_json(event)
                    # Broadcast to all other open connections too
                    for other in list(_connections):
                        if other is not websocket:
                            try:
                                await other.send_json(event)
                            except Exception:
                                _connections.remove(other)
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _connections:
            _connections.remove(websocket)
        logger.info("WebSocket disconnected (%d remaining)", len(_connections))
