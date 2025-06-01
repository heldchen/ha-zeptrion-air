import asyncio
import json
import logging
import time

from .const import ZEPTRION_AIR_WEBSOCKET_MESSAGE
import websockets

_LOGGER = logging.getLogger(__name__)

class ZeptrionAirWebsocketListener:
    def __init__(self, hostname: str, hass_instance, hub_unique_id: str):
        self._hostname = hostname
        self._hass = hass_instance
        self._hub_unique_id = hub_unique_id
        self._websocket = None
        self._task = None
        self._is_running = False
        self._ws_url = f"ws://{self._hostname}/zrap/ws"
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener instance created for {self._hostname}")

    async def _connect_with_retry(self):
        """Connect to websocket with exponential backoff retry logic."""
        backoff_time = 1
        max_backoff_time = 60

        while self._is_running:
            _LOGGER.debug(f"[{self._hostname}] Attempting to connect to websocket at {self._ws_url}...")
            try:
                # Ensure any previous connection is closed before attempting a new one
                if self._websocket:
                    _LOGGER.debug(f"[{self._hostname}] Closing pre-existing websocket connection before reconnecting.")
                    await self._close_websocket()

                self._websocket = await websockets.connect(self._ws_url, ping_interval=None, ping_timeout=None)
                _LOGGER.info(f"[{self._hostname}] Successfully connected to websocket at {self._ws_url}")
                return self._websocket # Return the active websocket connection
            except ConnectionRefusedError:
                _LOGGER.error(f"[{self._hostname}] Websocket connection refused for {self._ws_url}.")
            except websockets.exceptions.InvalidURI:
                _LOGGER.error(f"[{self._hostname}] Invalid Websocket URI: {self._ws_url}")
            except websockets.exceptions.WebSocketException as e:
                _LOGGER.error(f"[{self._hostname}] Websocket connection error for {self._ws_url}: {type(e).__name__} - {e}")
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Unexpected error connecting to websocket {self._ws_url}: {type(e).__name__} - {e}")

            # If connection failed, clean up and prepare for retry
            await self._close_websocket()

            if not self._is_running:
                _LOGGER.info(f"[{self._hostname}] Stop requested during connection attempt. Exiting connect_with_retry.")
                return None

            _LOGGER.info(f"[{self._hostname}] Websocket connection attempt failed. Waiting {backoff_time}s before reconnecting.")
            try:
                await asyncio.sleep(backoff_time)
            except asyncio.CancelledError:
                _LOGGER.info(f"[{self._hostname}] Sleep for backoff was cancelled. Likely stop requested.")
                return None

            backoff_time = min(max_backoff_time, backoff_time * 2)

        _LOGGER.info(f"[{self._hostname}] Exiting connect_with_retry because self._is_running is false.")
        return None

    async def listen(self):
        """Main websocket listener loop."""
        _LOGGER.info(f"[{self._hostname}] Main websocket listener loop started. self._is_running = {self._is_running}")

        while self._is_running:
            self._websocket = await self._connect_with_retry()

            if not self._websocket or not self._is_running:
                _LOGGER.info(f"[{self._hostname}] Connection could not be established or stop requested. Exiting listener loop.")
                break

            _LOGGER.info(f"[{self._hostname}] Websocket connection active. Entering message receiving loop.")
            try:
                async for message_raw in self._websocket:
                    if not self._is_running:
                        _LOGGER.info(f"[{self._hostname}] Stop requested during message processing in async for. Breaking from loop.")
                        break  # Exit the async for loop

                    # Message processing logic
                    try:
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
                    except websockets.exceptions.ConnectionClosed as e: # This might still occur if the connection drops mid-iteration
                        _LOGGER.warning(f"[{self._hostname}] Websocket connection closed during message processing (code: {e.code}, reason: {e.reason}). Will attempt to reconnect.")
                        await self._close_websocket() # Ensure cleanup
                        break # Break from async for to outer while loop for reconnection
                    except Exception as e: # Catch other unexpected errors during message processing
                        _LOGGER.error(f"[{self._hostname}] Error during websocket message processing: {type(e).__name__} - {e}. Will attempt to reconnect.")
                        await self._close_websocket() # Ensure cleanup
                        break # Break from async for to outer while loop for reconnection

                # This block will be reached if the async for loop exits cleanly (e.g., server closes connection gracefully)
                # or if a break statement inside the loop (due to error or stop request) is executed.
                if self._is_running:
                    _LOGGER.info(f"[{self._hostname}] Async for loop exited. Connection might have closed or stop was called. Will attempt to reconnect if still running.")
                else:
                    _LOGGER.info(f"[{self._hostname}] Async for loop exited due to stop request.")

            except websockets.exceptions.ConnectionClosed as e:
                # This handles cases where the connection is closed before or during the async for setup.
                _LOGGER.warning(f"[{self._hostname}] Websocket connection closed outside message processing loop (code: {e.code}, reason: {e.reason}). Will attempt to reconnect.")
                await self._close_websocket() # Ensure cleanup
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Unexpected error in message receiving logic wrapper: {type(e).__name__} - {e}")
                await self._close_websocket() # Ensure cleanup

            # If the async for loop broke (due to error or connection loss) or completed,
            # and we are still running, the outer while loop will call _connect_with_retry() again.
            # No explicit sleep or backoff here, as _connect_with_retry handles it.

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
            if eid1_data is None:
                _LOGGER.warning(f"[{self._hostname}] Received eid1 message with null data: {message_json}")
                return None

            channel = eid1_data.get('ch')
            value = eid1_data.get('val')

            if channel is None or value is None:
                _LOGGER.warning(f"[{self._hostname}] Received eid1 message with missing 'ch' or 'val': {message_json}")

            decoded_info.update({
                "type": "value_update",
                "channel": channel,
                "value": value,
                "source": "eid1",
                "hub_unique_id": self._hub_unique_id
            })
            return decoded_info
        elif 'eid2' in message_json:
            eid2_data = message_json['eid2']
            if eid2_data is None:
                _LOGGER.warning(f"[{self._hostname}] Received eid2 message with null data: {message_json}")
                return None

            bta_str = eid2_data.get('bta', '')
            # It's possible bta_str might be None if 'bta' key exists but value is null, though .get with default handles it.
            # However, if bta was critical and could be null, an explicit check:
            # if bta_str is None:
            #     _LOGGER.warning(f"[{self._hostname}] Received eid2 message with null 'bta': {message_json}")
            #     return None

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
                "bta_raw": bta_str,
                "hub_unique_id": self._hub_unique_id
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

    def is_alive(self) -> bool:
        """Check if the websocket listener is active and healthy."""
        if not self._is_running:
            _LOGGER.debug(f"[{self._hostname}] is_alive: False (not supposed to be running).")
            return False
        if not self._task or self._task.done():
            _LOGGER.debug(f"[{self._hostname}] is_alive: False (task is None or done).")
            return False
        if not self._websocket or not self._websocket.open:
            _LOGGER.debug(f"[{self._hostname}] is_alive: False (websocket is None or not open).")
            return False
        _LOGGER.debug(f"[{self._hostname}] is_alive: True.")
        return True

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
