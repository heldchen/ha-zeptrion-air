import asyncio
import json
import logging
import time
import websockets

_LOGGER = logging.getLogger(__name__)

class ZeptrionAirWebsocketListener:
    def __init__(self, hostname: str, hass_instance):
        self._hostname = hostname
        self._hass = hass_instance
        self._websocket = None
        self._task = None
        self._is_running = False
        # The legacy code refers to panel.port, but the issue specifies ws://<hostname>
        # which implies the default WebSocket port (80 for ws, 443 for wss).
        # If the device uses a non-standard port, this URL might need adjustment.
        self._ws_url = f"ws://{self._hostname}/zrap/ws" # Common path for websockets on devices
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener instance created for {self._hostname}") # ADDED

    async def _connect(self):
        _LOGGER.debug(f"[{self._hostname}] Attempting to connect to websocket at {self._ws_url}...") # MODIFIED
        try:
            # The legacy code used port from a 'panel' object.
            # Attempting standard path, adjust if known.
            self._websocket = await websockets.connect(self._ws_url)
            _LOGGER.info(f"[{self._hostname}] Successfully connected to websocket at {self._ws_url}")
            self._is_running = True
        except ConnectionRefusedError:
            _LOGGER.error(f"[{self._hostname}] Websocket connection refused for {self._ws_url}. Is the device online and WS enabled?")
            self._websocket = None
            self._is_running = False
        except websockets.exceptions.InvalidURI as e:
            _LOGGER.error(f"[{self._hostname}] Invalid Websocket URI: {self._ws_url} - {e}")
            self._websocket = None
            self._is_running = False
        except websockets.exceptions.WebSocketException as e: # Catch other websocket specific exceptions
            _LOGGER.error(f"[{self._hostname}] Websocket connection error for {self._ws_url}: {type(e).__name__} - {e}")
            self._websocket = None
            self._is_running = False
        except Exception as e: # General exceptions
            _LOGGER.error(f"[{self._hostname}] Unexpected error connecting to websocket {self._ws_url}: {type(e).__name__} - {e}")
            self._websocket = None
            self._is_running = False

    async def listen(self):
        _LOGGER.debug(f"[{self._hostname}] Listener invoked. Checking connection state.") # ADDED
        if not self._websocket or not self._is_running:
            _LOGGER.debug(f"[{self._hostname}] No active connection or not running, attempting to connect.") # ADDED
            await self._connect()
            if not self._websocket: # Still no connection after attempt
                _LOGGER.warning(f"[{self._hostname}] Could not establish websocket connection after _connect call. Listener will not proceed.") # MODIFIED
                # Implement a backoff retry mechanism if desired, for now, it will retry on next HA call if any.
                return

        _LOGGER.debug(f"[{self._hostname}] Starting listening loop...") # ADDED
        try:
            while self._is_running and self._websocket:
                try:
                    message_raw = await asyncio.wait_for(self._websocket.recv(), timeout=30.0) # Keepalive/timeout
                    status_time = time.time()
                    _LOGGER.debug(f"[{self._hostname}] Raw WS message: {message_raw}")
                    decoded_message = self._decode_message(message_raw, status_time)
                    if decoded_message:
                        _LOGGER.debug(f"[{self._hostname}] Decoded WS Message: {decoded_message}")
                        # Here, you would eventually dispatch this to an update coordinator or directly to entities
                        # For now, just logging as per the plan.
                except asyncio.TimeoutError:
                    #_LOGGER.debug(f"[{self._hostname}] Websocket recv timeout, sending ping.")
                    try:
                        # Zeptrion devices might not support standard WS pings,
                        # or might have a proprietary keepalive.
                        # This is a standard way to keep a connection alive if pongs are supported.
                        pong_waiter = await self._websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=10)
                        #_LOGGER.debug(f"[{self._hostname}] Ping successful.")
                    except Exception as e:
                        _LOGGER.warning(f"[{self._hostname}] Websocket ping failed or timed out: {e}. Connection might be stale.")
                        # Consider closing and reconnecting
                        await self._close_websocket()
                        # Attempt to reconnect by breaking and letting the outer loop handle it or by calling _connect directly
                        break # Break inner loop to trigger reconnect logic
                except websockets.exceptions.ConnectionClosed as e:
                    _LOGGER.warning(f"[{self._hostname}] Websocket connection closed: {e}")
                    self._is_running = False # Stop trying if connection is closed by server
                    break # Exit listen loop
                except Exception as e:
                    _LOGGER.error(f"[{self._hostname}] Error during websocket listening: {e}")
                    # Depending on the error, you might want to break or continue
                    await asyncio.sleep(5) # Wait a bit before trying to receive again
        finally:
            _LOGGER.debug(f"[{self._hostname}] Listener loop ended. Closing websocket.") # ADDED
            await self._close_websocket()

    def _decode_message(self, message_raw: str, status_time: float) -> dict | None:
        try:
            message_json = json.loads(message_raw)
        except json.JSONDecodeError:
            _LOGGER.warning(f"[{self._hostname}] Could not decode JSON from websocket message: {message_raw}")
            return None

        # Adapted from legacy Message class
        # It seems the legacy code expected two messages for button presses (eid2)
        # and one for value changes (eid1). This simple listener gets one at a time.
        # We'll log what we get.

        decoded_info = {
            "ip": self._hostname, # Assuming hostname is sufficient for identification
            "status_time": status_time,
            "raw_message": message_json
        }

        if 'eid1' in message_json: # Value change (e.g., dimmer level, blind position if reported)
            eid1_data = message_json['eid1']
            decoded_info.update({
                "type": "value_update", # Or "channel_value"
                "channel": eid1_data.get('ch'),
                "value": eid1_data.get('val'),
                "source": "eid1"
            })
            # Example: {'eid1': {'ch': 1, 'val': 50}}
            return decoded_info
        elif 'eid2' in message_json: # Button press event
            eid2_data = message_json['eid2']
            bta_str = eid2_data.get('bta', '') # format like "R.R.P.R.R.R"
            buttons_state = bta_str.split('.')
            pressed_button_index = -1
            try:
                pressed_button_index = buttons_state.index('P') # 'P' for pressed
            except ValueError:
                # Could be 'R' for released, or other states.
                # The legacy code paired a 'P' message with a subsequent 'R' message.
                # This listener handles them as they come.
                pass # No 'P' found

            decoded_info.update({
                "type": "button_event", # Or "button_press_raw"
                "button_states_array": buttons_state, # e.g. ['R', 'R', 'P', 'R', 'R', 'R']
                "pressed_button_index": pressed_button_index, # 0-indexed if found
                "source": "eid2",
                "bta_raw": bta_str
            })
            # Example: {'eid2': {'bta': 'R.R.P.R.R.R'}}
            return decoded_info
        else:
            _LOGGER.debug(f"[{self._hostname}] Unknown websocket message structure: {message_json}")
            return None # Or return with a generic "unknown_event" type

    async def start(self):
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener start() called.") # ADDED
        if not self._task or self._task.done():
            _LOGGER.info(f"[{self._hostname}] Starting websocket listener task.") # MODIFIED from debug to info for better visibility
            # Ensure previous connection is closed before starting a new one
            await self._close_websocket()
            # Reset is_running for a fresh start
            self._is_running = True # Set true before creating task
            self._task = self._hass.loop.create_task(self.listen())
            _LOGGER.debug(f"[{self._hostname}] Websocket listener task created.") # ADDED
        else:
            _LOGGER.debug(f"[{self._hostname}] Websocket listener task already running or not yet done.") # MODIFIED

    async def stop(self):
        _LOGGER.debug(f"[{self._hostname}] ZeptrionAirWebsocketListener stop() called.") # ADDED
        _LOGGER.info(f"[{self._hostname}] Stopping websocket listener.")
        self._is_running = False # Signal listen loop to stop
        if self._websocket:
            await self._close_websocket()
        if self._task and not self._task.done():
            _LOGGER.debug(f"[{self._hostname}] Cancelling listener task.") # ADDED
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                _LOGGER.debug(f"[{self._hostname}] Websocket listener task cancelled successfully.") # MODIFIED
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Error during websocket task cancellation: {e}")
        self._task = None
        _LOGGER.debug(f"[{self._hostname}] Websocket listener fully stopped.")

    async def _close_websocket(self):
        _LOGGER.debug(f"[{self._hostname}] _close_websocket() called. Current state: _websocket is {'set' if self._websocket else 'None'}") # ADDED
        if self._websocket:
            try:
                await self._websocket.close()
                _LOGGER.debug(f"[{self._hostname}] Websocket connection actually closed.") # MODIFIED
            except Exception as e:
                _LOGGER.error(f"[{self._hostname}] Error closing websocket: {e}")
            finally:
                self._websocket = None
                _LOGGER.debug(f"[{self._hostname}] _websocket attribute set to None.") # ADDED
        else:
            _LOGGER.debug(f"[{self._hostname}] No active websocket to close.") # ADDED
