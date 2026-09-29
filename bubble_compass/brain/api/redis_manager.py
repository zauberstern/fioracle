"""Redis-backed WebSocket connection manager."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RedisWebSocketManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None
        self._pubsub = None
        self._local_connections: dict[str, set] = defaultdict(set)
        self._listener_task: asyncio.Task | None = None
        self._memory_bus: dict[str, list[dict]] = defaultdict(list)

    async def connect(self) -> None:
        try:
            import redis.asyncio as redis

            client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.25,
            )
            await client.ping()
            self._redis = client
            self._pubsub = self._redis.pubsub()
            self._listener_task = asyncio.create_task(self._listen())
            logger.info("Redis WebSocket manager connected")
        except Exception as exc:
            logger.warning("Redis unavailable (%s); using in-process fan-out", exc)
            self._redis = None
            self._pubsub = None

    async def disconnect(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub is not None:
            await self._pubsub.close()
        if self._redis is not None:
            await self._redis.close()

    def _channel_name(self, asset: str) -> str:
        return f"bubble_compass:{asset}"

    async def subscribe(self, asset: str, websocket) -> None:
        self._local_connections[asset].add(websocket)
        if self._pubsub is not None and len(self._local_connections[asset]) == 1:
            await self._pubsub.subscribe(self._channel_name(asset))

    async def unsubscribe(self, asset: str, websocket) -> None:
        self._local_connections[asset].discard(websocket)
        if self._pubsub is not None and not self._local_connections[asset]:
            await self._pubsub.unsubscribe(self._channel_name(asset))

    async def publish(self, asset: str, message: dict) -> None:
        payload = json.dumps(message)
        if self._redis is not None:
            await self._redis.publish(self._channel_name(asset), payload)
            return
        await self._relay(asset, payload)

    async def _relay(self, asset: str, data: str) -> None:
        dead = set()
        for ws in self._local_connections.get(asset, set()):
            try:
                await ws.send_text(data)
            except Exception as exc:
                logger.warning("Failed to send to WebSocket: %s", exc)
                dead.add(ws)
        for ws in dead:
            self._local_connections[asset].discard(ws)

    async def _listen(self) -> None:
        if self._pubsub is None:
            return
        try:
            async for message in self._pubsub.listen():
                if message.get("type") == "message":
                    channel = message["channel"]
                    asset = channel.split(":")[-1]
                    await self._relay(asset, message["data"])
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as exc:
            logger.error("Redis listener error: %s", exc)

    async def get_cached_state(self, asset: str) -> dict | None:
        if self._redis is not None:
            data = await self._redis.get(f"bubble_compass:state:{asset}")
            return json.loads(data) if data else None
        bus = self._memory_bus.get(asset)
        return bus[-1] if bus else None

    async def set_cached_state(self, asset: str, state: dict) -> None:
        if self._redis is not None:
            await self._redis.set(f"bubble_compass:state:{asset}", json.dumps(state))
        else:
            self._memory_bus[asset].append(state)
