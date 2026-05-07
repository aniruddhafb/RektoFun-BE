"""Background Birdeye websocket price logger."""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from typing import Any

from websockets import connect
from websockets.exceptions import WebSocketException

from config import Settings


class BirdeyePriceLogger:
    """Log live Birdeye price updates while the FastAPI app is running."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task or not self._settings.birdeye_api_key:
            if not self._settings.birdeye_api_key:
                print("Birdeye price logger is disabled: BIRDEYE_API_KEY is not set.")
            return

        self._task = asyncio.create_task(self._run(), name="birdeye-price-logger")

    async def stop(self) -> None:
        if not self._task:
            return

        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        retry_delay_seconds = 5

        while True:
            try:
                await self._stream_prices()
            except asyncio.CancelledError:
                raise
            except (OSError, WebSocketException, json.JSONDecodeError) as exc:
                print(f"Birdeye websocket error: {exc}")
                print(f"Retrying Birdeye websocket connection in {retry_delay_seconds} seconds...")
                await asyncio.sleep(retry_delay_seconds)

    async def _stream_prices(self) -> None:
        chain = self._settings.birdeye_chain
        address = self._settings.birdeye_price_address
        currency = self._settings.birdeye_price_currency
        chart_type = self._settings.birdeye_chart_type
        url = f"wss://public-api.birdeye.so/socket/{chain}?x-api-key={self._settings.birdeye_api_key}"
        subscription_message = {
            "type": "SUBSCRIBE_PRICE",
            "data": {
                "queryType": "simple",
                "chartType": chart_type,
                "address": address,
                "currency": currency,
            },
        }

        print(f"Connecting to Birdeye websocket for {chain}:{address} ({currency})")

        async with connect(url, ping_interval=20, ping_timeout=20) as websocket:
            print("Birdeye websocket connected.")
            await websocket.send(json.dumps(subscription_message))
            print(
                f"Subscribed to Birdeye price updates for address={address} "
                f"currency={currency} chartType={chart_type}"
            )

            async for raw_message in websocket:
                self._log_price_update(raw_message)

    def _log_price_update(self, raw_message: str) -> None:
        payload = json.loads(raw_message)
        message_type = payload.get("type", "UNKNOWN")

        if message_type != "PRICE_DATA":
            print(f"Birdeye message type: {message_type} | payload={payload}")
            return

        if not payload.get("data"):
            return

        price = self._extract_price(payload["data"])
        if price is None:
            print(f"Birdeye price update received: {payload}")
            return

        unix_time = payload["data"].get("unixTime")
        symbol = payload["data"].get("symbol", "unknown")
        event_type = payload["data"].get("eventType", "unknown")
        timestamp = self._format_timestamp(unix_time)
        print(
            "Birdeye live price: "
            f"{price} | symbol={symbol} | event={event_type} "
            f"| address={self._settings.birdeye_price_address} "
            f"| currency={self._settings.birdeye_price_currency} | ts={timestamp}"
        )

    @staticmethod
    def _extract_price(data: dict[str, Any]) -> Any:
        for key in ("c", "price", "value", "close"):
            if key in data:
                return data[key]
        return None

    @staticmethod
    def _format_timestamp(unix_time: Any) -> str:
        if not unix_time:
            return "n/a"

        try:
            return datetime.fromtimestamp(int(unix_time), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return str(unix_time)
