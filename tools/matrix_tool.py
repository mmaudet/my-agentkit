"""Matrix messaging tool for reading and sending messages via Matrix protocol.

Registers LLM-callable tools:
- ``matrix_get_notifications`` -- get recent highlight notifications (mentions, keywords)
- ``matrix_list_rooms`` -- list joined rooms, optionally filtered by name
- ``matrix_read_messages`` -- read recent messages from a room
- ``matrix_send_message`` -- send a message to a room

Authentication uses a Matrix access token via ``MATRIX_ACCESS_TOKEN`` env var.
The homeserver URL is read from ``MATRIX_HOMESERVER``.
"""

import asyncio
import json
import logging
import os
import urllib.parse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _get_config():
    """Return (homeserver_url, access_token) from env vars at call time."""
    return (
        os.getenv("MATRIX_HOMESERVER", "").rstrip("/"),
        os.getenv("MATRIX_ACCESS_TOKEN", ""),
    )


def _get_headers(token: str = "") -> Dict[str, str]:
    if not token:
        _, token = _get_config()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _quote_room_id(room_id: str) -> str:
    return urllib.parse.quote(room_id, safe="")


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def _async_get_notifications(limit: int = 20, only_highlights: bool = True) -> Dict[str, Any]:
    """Fetch recent notifications."""
    import aiohttp

    url_base, token = _get_config()
    params = f"limit={limit}"
    if only_highlights:
        params += "&only=highlight"
    url = f"{url_base}/_matrix/client/v3/notifications?{params}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_get_headers(token), timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    notifications = []
    for n in data.get("notifications", []):
        event = n.get("event", {})
        notifications.append({
            "sender": event.get("sender", ""),
            "room_id": n.get("room_id", ""),
            "body": event.get("content", {}).get("body", "")[:200],
            "timestamp": event.get("origin_server_ts", 0),
        })

    return {"count": len(notifications), "notifications": notifications}


async def _async_list_rooms(filter_name: Optional[str] = None) -> Dict[str, Any]:
    """List joined rooms with names."""
    import aiohttp

    url_base, token = _get_config()
    url = f"{url_base}/_matrix/client/v3/joined_rooms"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_get_headers(token), timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    rooms = []
    room_ids = data.get("joined_rooms", [])

    async with aiohttp.ClientSession() as session:
        for room_id in room_ids:
            try:
                name_url = f"{url_base}/_matrix/client/v3/rooms/{_quote_room_id(room_id)}/state/m.room.name"
                async with session.get(name_url, headers=_get_headers(token), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        name_data = await resp.json()
                        name = name_data.get("name", "")
                    else:
                        name = ""
            except Exception:
                name = ""

            if filter_name and filter_name.lower() not in name.lower():
                continue
            rooms.append({"room_id": room_id, "name": name})

    return {"count": len(rooms), "rooms": rooms}


async def _async_read_messages(room_id: str, limit: int = 20) -> Dict[str, Any]:
    """Read recent messages from a room."""
    import aiohttp

    url_base, token = _get_config()
    url = f"{url_base}/_matrix/client/v3/rooms/{_quote_room_id(room_id)}/messages?dir=b&limit={limit}&filter=%7B%22types%22%3A%5B%22m.room.message%22%5D%7D"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=_get_headers(token), timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    messages = []
    for event in data.get("chunk", []):
        content = event.get("content", {})
        messages.append({
            "sender": event.get("sender", ""),
            "body": content.get("body", "")[:500],
            "type": content.get("msgtype", ""),
            "timestamp": event.get("origin_server_ts", 0),
        })

    messages.reverse()
    return {"count": len(messages), "room_id": room_id, "messages": messages}


async def _async_send_message(room_id: str, body: str, formatted: bool = False) -> Dict[str, Any]:
    """Send a text message to a room."""
    import aiohttp
    import time

    url_base, token = _get_config()
    txn_id = f"hermes_{int(time.time() * 1000)}"
    url = f"{url_base}/_matrix/client/v3/rooms/{_quote_room_id(room_id)}/send/m.room.message/{txn_id}"

    payload: Dict[str, Any] = {"msgtype": "m.text", "body": body}
    if formatted:
        payload["format"] = "org.matrix.custom.html"
        payload["formatted_body"] = body

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=_get_headers(token), json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    return {"success": True, "event_id": data.get("event_id", ""), "room_id": room_id}


# ---------------------------------------------------------------------------
# Sync wrappers
# ---------------------------------------------------------------------------

def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    else:
        return asyncio.run(coro)


def _handle_get_notifications(args: dict, **kw) -> str:
    limit = args.get("limit", 20)
    only_highlights = args.get("only_highlights", True)
    try:
        result = _run_async(_async_get_notifications(limit=limit, only_highlights=only_highlights))
        return json.dumps({"result": result})
    except Exception as e:
        logger.error("matrix_get_notifications error: %s", e)
        return json.dumps({"error": f"Failed to get notifications: {e}"})


def _handle_list_rooms(args: dict, **kw) -> str:
    filter_name = args.get("filter_name")
    try:
        result = _run_async(_async_list_rooms(filter_name=filter_name))
        return json.dumps({"result": result})
    except Exception as e:
        logger.error("matrix_list_rooms error: %s", e)
        return json.dumps({"error": f"Failed to list rooms: {e}"})


def _handle_read_messages(args: dict, **kw) -> str:
    room_id = args.get("room_id", "")
    if not room_id:
        return json.dumps({"error": "Missing required parameter: room_id"})
    limit = args.get("limit", 20)
    try:
        result = _run_async(_async_read_messages(room_id=room_id, limit=limit))
        return json.dumps({"result": result})
    except Exception as e:
        logger.error("matrix_read_messages error: %s", e)
        return json.dumps({"error": f"Failed to read messages: {e}"})


def _handle_send_message(args: dict, **kw) -> str:
    room_id = args.get("room_id", "")
    body = args.get("body", "")
    if not room_id or not body:
        return json.dumps({"error": "Missing required parameters: room_id and body"})
    try:
        result = _run_async(_async_send_message(room_id=room_id, body=body))
        return json.dumps({"result": result})
    except Exception as e:
        logger.error("matrix_send_message error: %s", e)
        return json.dumps({"error": f"Failed to send message: {e}"})


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _check_matrix_available() -> bool:
    return bool(os.getenv("MATRIX_ACCESS_TOKEN"))


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

MATRIX_GET_NOTIFICATIONS_SCHEMA = {
    "name": "matrix_get_notifications",
    "description": (
        "Get recent Matrix notifications (mentions, highlights). "
        "Use this to check for pending messages that mention the user or require attention."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of notifications to return (default: 20).",
            },
            "only_highlights": {
                "type": "boolean",
                "description": "If true, only return highlight notifications (mentions, keywords). Default: true.",
            },
        },
        "required": [],
    },
}

MATRIX_LIST_ROOMS_SCHEMA = {
    "name": "matrix_list_rooms",
    "description": (
        "List Matrix rooms the user has joined. Optionally filter by room name. "
        "Returns room IDs and names. Use this to find a room before sending a message or reading messages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filter_name": {
                "type": "string",
                "description": "Filter rooms by name (case-insensitive substring match). Omit to list all rooms.",
            },
        },
        "required": [],
    },
}

MATRIX_READ_MESSAGES_SCHEMA = {
    "name": "matrix_read_messages",
    "description": (
        "Read recent messages from a Matrix room. Use matrix_list_rooms first to find the room_id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "room_id": {
                "type": "string",
                "description": "The Matrix room ID (e.g. '!abc123:server.com'). Get this from matrix_list_rooms.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of messages to return (default: 20).",
            },
        },
        "required": ["room_id"],
    },
}

MATRIX_SEND_MESSAGE_SCHEMA = {
    "name": "matrix_send_message",
    "description": (
        "Send a text message to a Matrix room. Use matrix_list_rooms first to find the room_id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "room_id": {
                "type": "string",
                "description": "The Matrix room ID to send to (e.g. '!abc123:server.com').",
            },
            "body": {
                "type": "string",
                "description": "The message text to send.",
            },
        },
        "required": ["room_id", "body"],
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

from tools.registry import registry

registry.register(
    name="matrix_get_notifications",
    toolset="matrix",
    schema=MATRIX_GET_NOTIFICATIONS_SCHEMA,
    handler=_handle_get_notifications,
    check_fn=_check_matrix_available,
    emoji="💬",
)

registry.register(
    name="matrix_list_rooms",
    toolset="matrix",
    schema=MATRIX_LIST_ROOMS_SCHEMA,
    handler=_handle_list_rooms,
    check_fn=_check_matrix_available,
    emoji="💬",
)

registry.register(
    name="matrix_read_messages",
    toolset="matrix",
    schema=MATRIX_READ_MESSAGES_SCHEMA,
    handler=_handle_read_messages,
    check_fn=_check_matrix_available,
    emoji="💬",
)

registry.register(
    name="matrix_send_message",
    toolset="matrix",
    schema=MATRIX_SEND_MESSAGE_SCHEMA,
    handler=_handle_send_message,
    check_fn=_check_matrix_available,
    emoji="💬",
)
