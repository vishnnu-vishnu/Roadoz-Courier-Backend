from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List, Optional
import json
import logging
from datetime import datetime
from app.utils.jwt import verify_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections, supporting broadcast and targeted messages."""

    def __init__(self):
        # Map of user_id -> list of active sockets (user may have multiple tabs)
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map of role -> list of user_ids
        self.role_map: Dict[str, List[str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, role: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

        if role not in self.role_map:
            self.role_map[role] = []
        if user_id not in self.role_map[role]:
            self.role_map[role].append(user_id)

        logger.info(f"WS connected: user={user_id} role={role} total={sum(len(v) for v in self.active_connections.values())}")

    def disconnect(self, websocket: WebSocket, user_id: str, role: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket) if hasattr(
                self.active_connections[user_id], "discard"
            ) else None
            try:
                self.active_connections[user_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # Clean role map
                if role in self.role_map and user_id in self.role_map[role]:
                    self.role_map[role].remove(user_id)
        logger.info(f"WS disconnected: user={user_id}")

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to all connections of a specific user."""
        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to {user_id}: {e}")

    async def broadcast_to_role(self, role: str, message: dict):
        """Broadcast a message to all users with a specific role."""
        for user_id in self.role_map.get(role, []):
            await self.send_to_user(user_id, message)

    async def broadcast_all(self, message: dict):
        """Broadcast to every connected client."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)

    @property
    def total_connections(self) -> int:
        return sum(len(v) for v in self.active_connections.values())


manager = ConnectionManager()


def _build_event(event_type: str, data: dict, sender_id: Optional[str] = None) -> dict:
    return {
        "type": event_type,
        "data": data,
        "sender_id": sender_id,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for real-time notifications.

    **Connect:** `ws://<host>/ws/notifications?token=<access_token>`

    **Events received from server:**
    ```json
    {"type": "login_notification", "data": {...}, "timestamp": "..."}
    {"type": "franchise_status",   "data": {...}, "timestamp": "..."}
    {"type": "otp_verified",       "data": {...}, "timestamp": "..."}
    {"type": "system_update",      "data": {...}, "timestamp": "..."}
    {"type": "ping",               "data": {},    "timestamp": "..."}
    ```

    **Events sent by client:**
    ```json
    {"type": "ping"}
    {"type": "subscribe", "topic": "franchise_updates"}
    ```
    """
    # Authenticate via query param token
    user_id = "anonymous"
    role = "guest"

    if token:
        payload = verify_access_token(token)
        if payload:
            user_id = payload.get("user_id", "anonymous")
            role = payload.get("role", "guest")
        else:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

    await manager.connect(websocket, user_id, role)

    # Send welcome event
    await websocket.send_json(
        _build_event(
            "connected",
            {
                "message": "Connected to notification service",
                "user_id": user_id,
                "role": role,
                "total_online": manager.total_connections,
            },
        )
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    _build_event("error", {"message": "Invalid JSON payload"})
                )
                continue

            event_type = msg.get("type", "")

            if event_type == "ping":
                await websocket.send_json(_build_event("pong", {"status": "ok"}))

            elif event_type == "subscribe":
                topic = msg.get("topic", "")
                await websocket.send_json(
                    _build_event("subscribed", {"topic": topic, "message": f"Subscribed to {topic}"})
                )

            elif event_type == "broadcast" and role == "super_admin":
                # Super admins can broadcast to all
                payload_data = msg.get("data", {})
                await manager.broadcast_all(
                    _build_event("system_update", payload_data, sender_id=user_id)
                )

            else:
                await websocket.send_json(
                    _build_event("error", {"message": f"Unknown event type: {event_type}"})
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, role)
        # Notify others if super_admin wants
        logger.info(f"WS disconnected cleanly: user={user_id}")
    except Exception as e:
        logger.error(f"WS error for user={user_id}: {e}")
        manager.disconnect(websocket, user_id, role)
