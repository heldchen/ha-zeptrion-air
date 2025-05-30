import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.entity_platform import async_get_current_platform

from custom_components.zeptrion_air.cover import ZeptrionAirBlind
from custom_components.zeptrion_air.api import ZeptrionAirApiClient
from custom_components.zeptrion_air.const import (
    DOMAIN,
    ZEPTRION_AIR_WEBSOCKET_MESSAGE,
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS,
    SERVICE_BLIND_RECALL_S1, # Keep existing service names if they are still relevant
    SERVICE_BLIND_RECALL_S2,
    SERVICE_BLIND_RECALL_S3,
    SERVICE_BLIND_RECALL_S4,
    # The prompt mentioned SERVICE_BLIND_UP_STEP and SERVICE_BLIND_DOWN_STEP
    # These seem to map to open_tilt and close_tilt which are now standard entity methods
    # If they are still custom services, they should be defined in const.py and imported here
)

MOCK_HUB_SERIAL = "ZAPP12345"
MOCK_HUB_NAME = "Zeptrion Hub"
MOCK_CHANNEL_ID = 1
OTHER_CHANNEL_ID = 2


@pytest.fixture
def mock_hass():
    """Mock Hass object with a mock event bus."""
    hass = MagicMock(spec=HomeAssistant)
    hass.bus = MagicMock()
    hass.bus.async_listen = MagicMock()
    return hass

@pytest.fixture
def mock_api_client():
    """Mock API client."""
    client = MagicMock(spec=ZeptrionAirApiClient)
    client.async_channel_open = AsyncMock()
    client.async_channel_close = AsyncMock()
    client.async_channel_stop = AsyncMock()
    client.async_channel_move_open = AsyncMock()  # Used by close_cover_tilt
    client.async_channel_move_close = AsyncMock() # Used by open_cover_tilt
    client.async_channel_recall_s1 = AsyncMock()
    client.async_channel_recall_s2 = AsyncMock()
    client.async_channel_recall_s3 = AsyncMock()
    client.async_channel_recall_s4 = AsyncMock()
    return client

@pytest.fixture
def mock_config_entry(mock_api_client):
    """Mock ConfigEntry."""
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.client = mock_api_client
    config_entry.data = {CONF_STEP_DURATION_MS: DEFAULT_STEP_DURATION_MS}
    config_entry.entry_id = "test_entry_id"
    return config_entry

@pytest.fixture
async def blind_entity_added(hass, mock_config_entry):
    """Fixture to create a ZeptrionAirBlind instance and add it to HASS."""
    device_info_for_blind = {
        "identifiers": {(DOMAIN, f"{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}")},
        "name": f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}",
        "via_device": (DOMAIN, MOCK_HUB_SERIAL),
        "model": "Zeptrion Air Channel Test Model", # Added model
        "manufacturer": "Test Manufacturer", # Added manufacturer
        "sw_version": "1.0" # Added sw_version
    }

    # Ensure hass.data is initialized for domain and entry_id
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][mock_config_entry.entry_id] = { # platform_data
        "hub_device_info": {"manufacturer": "Feller AG", "sw_version": "v1.2.3"},
        "identified_channels": [], # Not strictly needed for this unit test focus
        "entry_title": MOCK_HUB_NAME,
        "hub_serial": MOCK_HUB_SERIAL,
        "client": mock_config_entry.runtime_data.client # important for services
    }


    blind = ZeptrionAirBlind(
        config_entry=mock_config_entry,
        device_info_for_blind_entity=device_info_for_blind,
        channel_id=MOCK_CHANNEL_ID,
        hub_serial=MOCK_HUB_SERIAL,
        entry_title=MOCK_HUB_NAME,
        entity_base_slug=f"{MOCK_HUB_NAME.lower()}_blind_ch{MOCK_CHANNEL_ID}"
    )
    blind.hass = hass  # Assign the mock HASS instance

    # Mock entity_platform for service registration if needed for other tests
    # For these specific tests, async_added_to_hass mainly sets up the event listener
    with patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform", return_value=MagicMock()):
         await blind.async_added_to_hass() # This will setup the listener

    return blind

async def simulate_eid1_event(hass, blind_entity, channel_id, value):
    """Helper to simulate an EID1 websocket event."""
    event_data = {
        "ip": "mock_ip", # Not used by handler, but part of real event
        "status_time": 1234567890, # Not used by handler
        "raw_message": {"eid1": {"ch": channel_id, "val": value}}, # Not used by handler
        "type": "value_update", # Not used by handler directly
        "channel": channel_id,
        "value": value,
        "source": "eid1"
    }
    event = Event(ZEPTRION_AIR_WEBSOCKET_MESSAGE, event_data)

    # Directly call the handler. The listener should be set up by async_added_to_hass.
    # Access the listener callback from the mock if needed, or call handler directly.
    # For simplicity, we call the handler directly as we have the entity.
    await blind_entity.async_handle_websocket_message(event)


def test_cover_initial_state_updated(blind_entity_added):
    blind = blind_entity_added # Use the new fixture
    assert blind.name == f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}"
    assert blind.unique_id == f"zapp_{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}" # Updated format
    assert blind.is_closed is None
    assert blind.is_opening is None # Per __init__
    assert blind.is_closing is None # Per __init__
    assert blind._last_action is None
    assert blind.current_cover_position is None
    assert blind.supported_features == (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE |
        CoverEntityFeature.STOP |
        CoverEntityFeature.OPEN_TILT |
        CoverEntityFeature.CLOSE_TILT
    )

@pytest.mark.asyncio
async def test_async_open_cover_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_open_cover()
    client.async_channel_open.assert_called_once_with(MOCK_CHANNEL_ID)
    assert blind._last_action == "opening"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_opening is True
    assert blind.is_closing is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_async_close_cover_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover()
    client.async_channel_close.assert_called_once_with(MOCK_CHANNEL_ID)
    assert blind._last_action == "closing"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_closing is True
    assert blind.is_opening is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_closing is False
    assert blind.is_opening is False
    assert blind.is_closed is True

@pytest.mark.asyncio
async def test_async_open_cover_tilt_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_open_cover_tilt()
    client.async_channel_move_close.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)
    assert blind._last_action == "opening"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_opening is True
    assert blind.is_closing is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_async_close_cover_tilt_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover_tilt()
    client.async_channel_move_open.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)
    assert blind._last_action == "closing"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_closing is True
    assert blind.is_opening is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_closing is False
    assert blind.is_opening is False
    assert blind.is_closed is True


@pytest.mark.asyncio
async def test_quirk_close_interrupted_by_open(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    # 1. Initial close
    await blind.async_close_cover()
    assert blind._last_action == "closing"
    client.async_channel_close.assert_called_once()

    # 2. Blinds start closing
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_closing is True
    assert blind.is_opening is False

    # 3. User presses open (interrupt)
    await blind.async_open_cover()
    assert blind._last_action == "opening" # Action changes immediately
    client.async_channel_open.assert_called_once()

    # 4. Original close action sends "stopped" event
    # Because _last_action is now "opening", this "0" event will set is_closed to False.
    # This matches the quirk: "if I press 'down', but then before the blind finished closing press 'up',
    # the api call for 'up' will abort the closing action but _not_ actually trigger an opening action."
    # The 'eid1' "0" indicates the motor stopped. The state should reflect outcome of "opening"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False # Because _last_action was 'opening' when '0' arrived

    # 5. New open action sends "running" event
    # This would only happen if the 'open' command indeed started a new motor action.
    # Based on the quirk description, this might not happen.
    # "the api call for 'up' will abort the closing action but _not_ actually trigger an opening action."
    # If it does NOT trigger an opening action, then no "100" would come for "opening".
    # The test below assumes the API call *does* eventually lead to an opening action being reported.
    # If the device truly just stops and doesn't start opening, then this part of the test might not be accurate
    # to the device behavior, but it tests the code's reaction to the sequence of events.
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_opening is True
    assert blind.is_closing is False
    # is_closed should remain False as it's opening

@pytest.mark.asyncio
async def test_quirk_open_interrupted_by_close(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    # 1. Initial open
    await blind.async_open_cover()
    assert blind._last_action == "opening"
    client.async_channel_open.assert_called_once()

    # 2. Blinds start opening
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_opening is True
    assert blind.is_closing is False

    # 3. User presses close (interrupt)
    await blind.async_close_cover()
    assert blind._last_action == "closing" # Action changes immediately
    client.async_channel_close.assert_called_once()

    # 4. Original open action sends "stopped" event
    # Because _last_action is now "closing", this "0" event will set is_closed to True.
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True # Because _last_action was 'closing' when '0' arrived

    # 5. New close action sends "running" event (assuming it does)
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_closing is True
    assert blind.is_opening is False
    # is_closed should remain True as it's closing (or become undefined until next '0')

@pytest.mark.asyncio
async def test_async_stop_cover_sequence_while_closing(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    # Start closing
    await blind.async_close_cover()
    assert blind._last_action == "closing"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_closing is True
    assert blind.is_opening is False
    assert blind.is_closed is None # Or False, depending on initial state. Let's assume None.

    # Stop the cover
    await blind.async_stop_cover()
    client.async_channel_stop.assert_called_once_with(MOCK_CHANNEL_ID)
    assert blind._last_action == "stop"

    # Simulate the stop event from websocket
    # When _last_action is "stop", the is_closed state should not change based on the "0" message.
    # It should reflect the state it was in, or a "stopped partway" state.
    # The current logic for "stop" in handle_websocket_message:
    #   opening/closing = False. is_closed depends on previous _last_action ('opening' -> False, 'closing' -> True)
    # If current _last_action is 'stop', it doesn't modify is_closed.
    # So, we need to know what is_closed was before the "0" message for a "stop" action.
    # When async_stop_cover is called, _last_action becomes "stop".
    # If the blind was closing, and then stopped, it's now partially closed (so, not fully closed).
    # If the blind was opening, and then stopped, it's now partially open (so, not fully closed).

    # Let's trace:
    # 1. async_close_cover() -> _last_action = "closing"
    # 2. eid1 val="100" -> is_closing=True, is_opening=False. is_closed remains None.
    # 3. async_stop_cover() -> _last_action = "stop". (is_opening=False, is_closing=False - this is not done here but by eid1 "0")

    # Set a defined state for is_closed before simulating the stop event for clarity
    blind._attr_is_closed = False # Explicitly say it's not closed before stop

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    # If _last_action was "stop" when "0" arrived, is_closed is NOT changed by the handler.
    # It relies on the command (open/close) that was active *before* stop was pressed.
    # This is tricky. The prompt says: "is_closed state should reflect the state *before* the stop"
    # The current handler for "0":
    #   if self._last_action == "opening": self._attr_is_closed = False
    #   elif self._last_action == "closing": self._attr_is_closed = True
    # If _last_action is "stop" at the time of the "0" message, neither of these will hit for is_closed.
    # This means is_closed will retain the value it had *before* this "0" message.
    # If it was closing, _last_action was "closing". If a "0" came *then*, is_closed would be True.
    # But stop command changes _last_action to "stop" *before* the "0" comes.
    # So, the state of is_closed depends on what it was *before* the stop command's "0" message.
    # This seems like a potential area of ambiguity.
    # Let's assume the most recent "movement defining" action (open/close) should determine final state.
    # The handler for "0" should ideally use the action that was *stopped*.
    # However, `_last_action` is already "stop".
    # For now, test current implementation: is_closed should be what it was before this "0" event.
    assert blind.is_closed is False # As we set it before the "0" for stop.

@pytest.mark.asyncio
async def test_message_for_other_channel(mock_hass, blind_entity_added):
    blind = blind_entity_added
    initial_is_opening = blind.is_opening
    initial_is_closing = blind.is_closing
    initial_is_closed = blind.is_closed
    initial_last_action = blind._last_action

    await blind.async_open_cover() # Make _last_action "opening"
    assert blind._last_action == "opening"

    await simulate_eid1_event(mock_hass, blind, OTHER_CHANNEL_ID, "100") # Message for other channel

    # Assert no state change
    assert blind.is_opening is initial_is_opening # Should still be None or False, not True from this event
    assert blind.is_closing is initial_is_closing
    assert blind.is_closed is initial_is_closed
    assert blind._last_action == "opening" # Should not change from other channel's message

    # Check that actual opening state not affected by other channel's message
    # Send a "100" for the correct channel
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind.is_opening is True # Now it should be true
    assert blind._last_action == "opening"


# Example of how to test service registration if still needed (adjust to actual services)
# For now, the main focus is websocket handling.
# The original test_service_registration might be outdated if up_step/down_step are now tilts.

@patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform")
@pytest.mark.asyncio
async def test_existing_service_registration_updated(mock_async_get_current_platform, blind_entity_added, mock_hass):
    blind = blind_entity_added # Uses the new fixture that calls async_added_to_hass

    mock_platform_instance = MagicMock()
    mock_platform_instance.async_register_entity_service = MagicMock()
    mock_async_get_current_platform.return_value = mock_platform_instance
    
    # Call async_added_to_hass again on the same instance, but this time with the patched platform
    # Note: blind_entity_added already called it once. If the listener setup is idempotent or safe to recall, this is fine.
    # Alternatively, ensure the patch is active when blind_entity_added calls it.
    # For this test, we are focused on the service registration part of async_added_to_hass.
    
    # To ensure the platform is patched when async_added_to_hass is called by the fixture,
    # it might be better to make the fixture itself use the patch, or pass mock_platform_instance to it.
    # However, for this specific rewrite, let's assume the listener part is tested by other tests,
    # and here we just verify the service registration calls if async_added_to_hass were called with this patch active.

    # Since async_added_to_hass was already called by the fixture, let's reset the mock and call again.
    # This is not ideal but demonstrates testing this part.
    mock_hass.bus.async_listen.reset_mock() # Reset listener mock
    blind.hass.bus.async_listen.reset_mock()

    # Re-run the relevant part of async_added_to_hass or the full method
    # Forcing re-registration for test purposes:
    # Manually create a new platform mock for this specific test context
    current_platform_mock = MagicMock()
    current_platform_mock.async_register_entity_service = AsyncMock() # Use AsyncMock if the method being called is async
    mock_async_get_current_platform.return_value = current_platform_mock

    await blind.async_added_to_hass() # Call it again with the new mock_platform in place

    calls = current_platform_mock.async_register_entity_service.call_args_list
    registered_services_handlers = {call[0][0]: call[0][2] for call in calls}
    
    expected_services = {
        # SERVICE_BLIND_UP_STEP: "async_open_cover_tilt", # If these are the mappings
        # SERVICE_BLIND_DOWN_STEP: "async_close_cover_tilt", # If these are the mappings
        SERVICE_BLIND_RECALL_S1: "async_blind_recall_s1",
        SERVICE_BLIND_RECALL_S2: "async_blind_recall_s2",
        SERVICE_BLIND_RECALL_S3: "async_blind_recall_s3",
        SERVICE_BLIND_RECALL_S4: "async_blind_recall_s4",
    }
    
    for service_name, handler_name in expected_services.items():
        assert service_name in registered_services_handlers, f"Service {service_name} not registered"
        assert registered_services_handlers[service_name] == handler_name, f"Handler for {service_name} is not {handler_name}"

    # Verify that async_listen was called for ZEPTRION_AIR_WEBSOCKET_MESSAGE
    # The listener should have been set up by the fixture already.
    # If we reset and recalled async_added_to_hass, it would be called again.
    # blind.hass.bus.async_listen.assert_any_call(ZEPTRION_AIR_WEBSOCKET_MESSAGE, blind.async_handle_websocket_message)
    # Check call count if it should only be called once.
    # This depends on how async_on_remove and listener setup interact on multiple calls.
    # For this test, focusing on service registration. Event listener setup is implicitly tested by other tests.

# Ensure original tests for basic API calls still pass if structure is similar
@pytest.mark.asyncio
async def test_original_cover_open_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_open_cover()
    client.async_channel_open.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_close_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_close_cover()
    client.async_channel_close.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_stop_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_stop_cover()
    client.async_channel_stop.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_tilt_open_api_call(blind_entity_added, mock_config_entry): # Was async_blind_up_step
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_open_cover_tilt() # Changed from async_blind_up_step
    client.async_channel_move_close.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)

@pytest.mark.asyncio
async def test_original_cover_tilt_close_api_call(blind_entity_added, mock_config_entry): # Was async_blind_down_step
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_close_cover_tilt() # Changed from async_blind_down_step
    client.async_channel_move_open.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)

@pytest.mark.asyncio
async def test_original_cover_recall_s1_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_blind_recall_s1()
    client.async_channel_recall_s1.assert_called_once_with(MOCK_CHANNEL_ID)

# Add S2, S3, S4 if they were in original tests and are still relevant
@pytest.mark.asyncio
async def test_original_cover_recall_s2_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_blind_recall_s2()
    client.async_channel_recall_s2.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_recall_s3_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_blind_recall_s3()
    client.async_channel_recall_s3.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_recall_s4_api_call(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client
    await blind.async_blind_recall_s4()
    client.async_channel_recall_s4.assert_called_once_with(MOCK_CHANNEL_ID)

# The test_service_methods_exist might need adjustment if method names changed (e.g. up_step -> open_cover_tilt)
def test_service_methods_exist_updated(blind_entity_added):
    blind = blind_entity_added
    assert hasattr(blind, "async_open_cover_tilt")
    assert hasattr(blind, "async_close_cover_tilt")
    assert hasattr(blind, "async_blind_recall_s1")
    assert hasattr(blind, "async_blind_recall_s2")
    assert hasattr(blind, "async_blind_recall_s3")
    assert hasattr(blind, "async_blind_recall_s4")

# Final check on the quirk for close interrupted by open, focusing on the state when "0" arrives for the aborted action.
# The key is that _last_action was changed to "opening" by the second command BEFORE the "0" for the first command arrives.
@pytest.mark.asyncio
async def test_quirk_close_interrupted_by_open_final_state_check(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added

    await blind.async_close_cover() # _last_action = "closing"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_closing = True

    await blind.async_open_cover() # _last_action = "opening"

    # eid1 "0" arrives, originating from the aborted "close" command.
    # At this point, _last_action is "opening".
    # Handler logic: if self._last_action == "opening": self._attr_is_closed = False
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False # Correctly set by "0"
    assert blind.is_closing is False # Correctly set by "0"
    assert blind.is_closed is False # Because _last_action was "opening"

# Final check on the quirk for open interrupted by close.
@pytest.mark.asyncio
async def test_quirk_open_interrupted_by_close_final_state_check(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added

    await blind.async_open_cover() # _last_action = "opening"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_opening = True

    await blind.async_close_cover() # _last_action = "closing"

    # eid1 "0" arrives, originating from the aborted "open" command.
    # At this point, _last_action is "closing".
    # Handler logic: elif self._last_action == "closing": self._attr_is_closed = True
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False # Correctly set by "0"
    assert blind.is_closing is False # Correctly set by "0"
    assert blind.is_closed is True # Because _last_action was "closing"

# Test stop behavior when _last_action is "stop" and a "0" event comes.
# This tests that is_closed is not affected by "0" if current _last_action is "stop".
@pytest.mark.asyncio
async def test_stop_cover_then_event_zero(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added

    # Scenario 1: Was closing, then stopped
    await blind.async_close_cover() # _last_action = "closing"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_closing = True
    blind._attr_is_closed = False # Assume it was not fully closed yet

    await blind.async_stop_cover() # _last_action = "stop"

    # Store current is_closed before "0" event
    is_closed_before_zero_event = blind.is_closed # Should be False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0") # eid1 "0" with _last_action = "stop"

    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed == is_closed_before_zero_event # is_closed should NOT change

    # Scenario 2: Was opening, then stopped
    await blind.async_open_cover() # _last_action = "opening"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_opening = True
    blind._attr_is_closed = True # Assume it was closed before opening

    await blind.async_stop_cover() # _last_action = "stop"

    is_closed_before_zero_event = blind.is_closed # Should be True

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0") # eid1 "0" with _last_action = "stop"

    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed == is_closed_before_zero_event # is_closed should NOT change

# Test that hass.data is correctly mocked/used by the entity for client access
@pytest.mark.asyncio
async def test_hass_data_client_access(blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    # Check if the client used by the entity is the one from hass.data (via config_entry.runtime_data)
    assert blind.config_entry.runtime_data.client == mock_config_entry.runtime_data.client
    # Perform an action that uses the client to ensure it's callable
    await blind.async_open_cover()
    mock_config_entry.runtime_data.client.async_channel_open.assert_called_with(MOCK_CHANNEL_ID)

# Test that the listener is actually registered with the HASS event bus
@pytest.mark.asyncio
async def test_event_listener_registration(mock_hass, blind_entity_added):
    blind = blind_entity_added # Fixture calls async_added_to_hass
    # Check that async_listen was called correctly on the mock_hass bus object
    mock_hass.bus.async_listen.assert_called_once_with(
        ZEPTRION_AIR_WEBSOCKET_MESSAGE,
        blind.async_handle_websocket_message
    )

# Test that async_on_remove is correctly called during setup for cleanup
# This is implicitly part of async_added_to_hass if it calls self.async_on_remove(...)
# We can mock async_on_remove to check if it's called.
@pytest.mark.asyncio
async def test_async_on_remove_called(mock_hass):
    # Create a new blind instance for this test to control async_added_to_hass call
    mock_config_entry_local = MagicMock(spec=ConfigEntry)
    mock_config_entry_local.runtime_data = MagicMock()
    mock_config_entry_local.runtime_data.client = MagicMock(spec=ZeptrionAirApiClient)
    mock_config_entry_local.data = {CONF_STEP_DURATION_MS: DEFAULT_STEP_DURATION_MS}
    mock_config_entry_local.entry_id = "test_on_remove_entry_id"

    device_info_for_blind = {
        "identifiers": {(DOMAIN, f"{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}")},
        "name": f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}",
    }
    blind = ZeptrionAirBlind(
        config_entry=mock_config_entry_local,
        device_info_for_blind_entity=device_info_for_blind,
        channel_id=MOCK_CHANNEL_ID,
        hub_serial=MOCK_HUB_SERIAL,
        entry_title=MOCK_HUB_NAME,
        entity_base_slug=f"{MOCK_HUB_NAME.lower()}_blind_ch{MOCK_CHANNEL_ID}"
    )
    blind.hass = mock_hass
    blind.async_on_remove = MagicMock() # Mock async_on_remove for this instance

    with patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform", return_value=MagicMock()):
        await blind.async_added_to_hass()

    blind.async_on_remove.assert_called_once()
    # We can also check what it was called with, if important:
    # args, _ = blind.async_on_remove.call_args
    # assert args[0] == mock_hass.bus.async_listen(...) # This is a bit complex to assert directly with the callback

# test_quirk_close_interrupted_by_open has a subtle point:
# "the api call for 'up' will abort the closing action but _not_ actually trigger an opening action."
# This means after `await blind.async_open_cover()` (which aborts close), there might NOT be an eid1="100" for "opening".
# The blind might just stop. If so, the final state would be based on the "0" from the aborted close,
# with _last_action="opening", leading to is_closed=False.
# The current test `test_quirk_close_interrupted_by_open` *does* simulate a subsequent eid1="100" for opening.
# This is fine for testing the code's reaction *if* such an event occurs.
# If the device behaves differently (no second "100"), the state would be:
# open=F, close=F, closed=F.

# Add a test for the scenario where the interrupting open does NOT send a new "100"
@pytest.mark.asyncio
async def test_quirk_close_interrupted_by_open_no_second_100(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover() # _last_action = "closing"
    client.async_channel_close.assert_called_once()
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_closing = True

    await blind.async_open_cover() # _last_action = "opening", aborts close
    client.async_channel_open.assert_called_once()

    # eid1 "0" from aborted close. _last_action is "opening".
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False # Because _last_action was 'opening' when '0' arrived

    # No further "100" event for opening is simulated.
    # State should remain: opening=False, closing=False, is_closed=False
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_quirk_open_interrupted_by_close_no_second_100(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_open_cover() # _last_action = "opening"
    client.async_channel_open.assert_called_once()
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100") # is_opening = True

    await blind.async_close_cover() # _last_action = "closing", aborts open
    client.async_channel_close.assert_called_once()

    # eid1 "0" from aborted open. _last_action is "closing".
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True # Because _last_action was 'closing' when '0' arrived

    # No further "100" event for closing is simulated.
    # State should remain: opening=False, closing=False, is_closed=True
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True
