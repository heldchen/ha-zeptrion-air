import asyncio
import json
import logging
import time

from .const import ZEPTRION_AIR_WEBSOCKET_MESSAGE
import websockets

_LOGGER = logging.getLogger(__name__)

class ZeptrionAirWebsocketListener:
    def __init__(self, hostname: str, hass_instance):
        self._hostname = hostname
        self._hass = hass_instance
        self._websocket = None
        self._task = None
        self._is_running = False
        self._ws_url = f"ws://{self._hostname}/zrap/ws"
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener instance created for {self._hostname}")

    async def _connect(self):
        """Connect to websocket and return success status."""
        _LOGGER.debug(f"[{self._hostname}] Attempting to connect to websocket at {self._ws_url}...")
        try:
            if self._websocket:
                _LOGGER.debug(f"[{self._hostname}] Closing pre-existing websocket connection before reconnecting.")
                await self._close_websocket()

            self._websocket = await websockets.connect(self._ws_url, ping_interval=25, ping_timeout=20)
            _LOGGER.info(f"[{self._hostname}] Successfully connected to websocket at {self._ws_url}")
            return True
        except ConnectionRefusedError:
            _LOGGER.error(f"[{self._hostname}] Websocket connection refused for {self._ws_url}.")
        except websockets.exceptions.InvalidURI:
            _LOGGER.error(f"[{self._hostname}] Invalid Websocket URI: {self._ws_url}")
        except websockets.exceptions.WebSocketException as e:
            _LOGGER.error(f"[{self._hostname}] Websocket connection error for {self._ws_url}: {type(e).__name__} - {e}")
        except Exception as e:
            _LOGGER.error(f"[{self._hostname}] Unexpected error connecting to websocket {self._ws_url}: {type(e).__name__} - {e}")

        await self._close_websocket()
        return False

    async def listen(self):
        """Main websocket listener loop with reconnection logic."""
        _LOGGER.info(f"[{self._hostname}] Main websocket listener loop started. self._is_running = {self._is_running}")
        backoff_time = 5
        max_backoff_time = 60

        while self._is_running:
            connection_successful = await self._connect()

            if connection_successful and self._websocket:
                _LOGGER.info(f"[{self._hostname}] Websocket connection active. Entering message receiving loop.")
                backoff_time = 5

                try:
                    while self._is_running and self._websocket:
                        try:
                            message_raw = await asyncio.wait_for(self._websocket.recv(), timeout=60.0)
                            status_time = time.time()
                            _LOGGER.debug(f"[{self._hostname}] Raw WS message: {message_raw}")
                            decoded_message = self._decode_message(message_raw, status_time)
                            if decoded_message:
                                _LOGGER.debug(f"[{self._hostname}] Decoded WS Message: {decoded_message}")
                                if decoded_message.get("source") == "eid1":
                                    self._hass.bus.async_fire(
                                        ZEPTRION_AIR_WEBSOCKET_MESSAGE,
                                        decoded_message
                                    )

                        except asyncio.TimeoutError:
                            _LOGGER.debug(f"[{self._hostname}] Websocket recv timed out. Checking connection with a ping.")
                            try:
                                pong_waiter = await self._websocket.ping()
                                await asyncio.wait_for(pong_waiter, timeout=10)
                                _LOGGER.debug(f"[{self._hostname}] Ping successful after recv timeout.")
                            except Exception as e:
                                _LOGGER.warning(f"[{self._hostname}] Websocket ping failed after recv timeout: {type(e).__name__} - {e}. Connection likely lost.")
                                await self._close_websocket()
                                break

                        except websockets.exceptions.ConnectionClosed as e:
                            _LOGGER.warning(f"[{self._hostname}] Websocket connection closed (code: {e.code}, reason: {e.reason}). Will attempt to reconnect.")
                            await self._close_websocket()
                            break

                        except Exception as e:
                            _LOGGER.error(f"[{self._hostname}] Error during websocket message listening: {type(e).__name__} - {e}. Will attempt to reconnect.")
                            await self._close_websocket()
                            break

                    if not self._is_running:
                        _LOGGER.info(f"[{self._hostname}] Listener stop requested while in message loop or after connection loss.")
                        break

                except Exception as e:
                    _LOGGER.error(f"[{self._hostname}] Unexpected error in message receiving logic: {type(e).__name__} - {e}")
                    await self._close_websocket()

            if self._is_running:
                _LOGGER.info(f"[{self._hostname}] Websocket connection attempt failed or connection lost. Waiting {backoff_time}s before reconnecting.")
                await self._close_websocket()
                await asyncio.sleep(backoff_time)
                backoff_time = min(max_backoff_time, backoff_time * 2)
            else:
                 _LOGGER.info(f"[{self._hostname}] Stop requested. Exiting main listener loop.")

        _LOGGER.info(f"[{self._hostname}] Websocket listener has fully stopped.")
        await self._close_websocket()

    def _decode_message(self, message_raw: str, status_time: float) -> dict | None:
        """Decode websocket message and return structured data."""
        try:
            message_json = json.loads(message_raw)
        except json.JSONDecodeError:
            _LOGGER.warning(f"[{self._hostname}] Could not decode JSON from websocket message: {message_raw}")
            return None

        decoded_info = {
            "ip": self._hostname,
            "status_time": status_time,
            "raw_message": message_json
        }

        if 'eid1' in message_json:
            eid1_data = message_json['eid1']
            decoded_info.update({
                "type": "value_update",
                "channel": eid1_data.get('ch'),
                "value": eid1_data.get('val'),
                "source": "eid1"
            })
            return decoded_info
        elif 'eid2' in message_json:
            eid2_data = message_json['eid2']
            bta_str = eid2_data.get('bta', '')
            buttons_state = bta_str.split('.')
            pressed_button_index = -1
            try:
                pressed_button_index = buttons_state.index('P')
            except ValueError:
                pass

            decoded_info.update({
                "type": "button_event",
                "button_states_array": buttons_state,
                "pressed_button_index": pressed_button_index,
                "source": "eid2",
                "bta_raw": bta_str
            })
            return decoded_info
        else:
            _LOGGER.debug(f"[{self._hostname}] Unknown websocket message structure: {message_json}")
            return None

    async def start(self):
        """Start the websocket listener."""
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener start() called.")
        if not self._task or self._task.done():
            self._is_running = True
            _LOGGER.info(f"[{self._hostname}] Creating and starting websocket listener task.")
            await self._close_websocket()
            self._task = self._hass.loop.create_task(self.listen())
            _LOGGER.debug(f"[{self._hostname}] Websocket listener task created.")
        else:
            _LOGGER.debug(f"[{self._hostname}] Websocket listener task already running or not yet done.")

    async def stop(self):
        """Stop the websocket listener."""
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener stop() called.")
        self._is_running = False

        if self._task and not self._task.done():
            _LOGGER.info(f"[{self._hostname}] Cancelling listener task.")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                _LOGGER.debug(f"[{self._hostname}] Websocket listener task cancelled successfully.")
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Error caught during task cancellation/await: {type(e).__name__} - {e}")
        else:
            _LOGGER.debug(f"[{self._hostname}] Listener task was not running or already done.")

        await self._close_websocket()
        self._task = None
        _LOGGER.info(f"[{self._hostname}] Websocket listener fully stopped and cleaned up.")

    async def _close_websocket(self):
        """Close websocket connection and cleanup."""
        _LOGGER.debug(f"[{self._hostname}] _close_websocket() called. Current state: _websocket is {'set' if self._websocket else 'None'}")
        if self._websocket:
            try:
                await self._websocket.close()
                _LOGGER.debug(f"[{self._hostname}] Websocket connection actually closed.")
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Error closing websocket: {type(e).__name__} - {e}")
            finally:
                self._websocket = None
                _LOGGER.debug(f"[{self._hostname}] _websocket attribute set to None.")
        else:
            _LOGGER.debug(f"[{self._hostname}] No active websocket to close in _close_websocket.")
