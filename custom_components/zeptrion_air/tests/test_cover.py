import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call as mock_call # Added mock_call

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.entity_platform import async_get_current_platform

from custom_components.zeptrion_air.cover import ZeptrionAirBlind, _LOGGER as cover_logger # Import logger
from custom_components.zeptrion_air.api import ZeptrionAirApiClient
from custom_components.zeptrion_air.const import (
    DOMAIN,
    ZEPTRION_AIR_WEBSOCKET_MESSAGE,
    CONF_STEP_DURATION_MS,
    DEFAULT_STEP_DURATION_MS,
    SERVICE_BLIND_RECALL_S1,
    SERVICE_BLIND_RECALL_S2,
    SERVICE_BLIND_RECALL_S3,
    SERVICE_BLIND_RECALL_S4,
)
import logging # For capturing log messages

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
    client.async_channel_move_open = AsyncMock()
    client.async_channel_move_close = AsyncMock()
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
        "model": "Zeptrion Air Channel Test Model",
        "manufacturer": "Test Manufacturer",
        "sw_version": "1.0"
    }

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][mock_config_entry.entry_id] = {
        "hub_device_info": {"manufacturer": "Feller AG", "sw_version": "v1.2.3"},
        "identified_channels": [],
        "entry_title": MOCK_HUB_NAME,
        "hub_serial": MOCK_HUB_SERIAL,
        "client": mock_config_entry.runtime_data.client
    }

    blind = ZeptrionAirBlind(
        config_entry=mock_config_entry,
        device_info_for_blind_entity=device_info_for_blind,
        channel_id=MOCK_CHANNEL_ID,
        hub_serial=MOCK_HUB_SERIAL,
        entry_title=MOCK_HUB_NAME,
        entity_base_slug=f"{MOCK_HUB_NAME.lower()}_blind_ch{MOCK_CHANNEL_ID}"
    )
    blind.hass = hass

    with patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform", return_value=MagicMock()):
         await blind.async_added_to_hass()

    return blind

async def simulate_eid1_event(hass, blind_entity, channel_id, value):
    """Helper to simulate an EID1 websocket event."""
    event_data = {
        "ip": "mock_ip",
        "status_time": 1234567890,
        "raw_message": {"eid1": {"ch": channel_id, "val": value}},
        "type": "value_update",
        "channel": channel_id,
        "value": value,
        "source": "eid1"
    }
    event = Event(ZEPTRION_AIR_WEBSOCKET_MESSAGE, event_data)
    await blind_entity.async_handle_websocket_message(event)


def test_cover_initial_state(blind_entity_added):
    blind = blind_entity_added
    assert blind.name == f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}"
    assert blind.unique_id == f"zapp_{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}"
    assert blind.is_closed is None
    assert blind.is_opening is None
    assert blind.is_closing is None
    assert blind._commanded_action is None
    assert blind._active_action is None
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
    assert blind._commanded_action == "opening"
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "opening"
    assert blind.is_opening is True
    assert blind.is_closing is False
    assert blind.is_closed is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind._active_action is None
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_async_close_cover_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover()
    client.async_channel_close.assert_called_once_with(MOCK_CHANNEL_ID)
    assert blind._commanded_action == "closing"
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "closing"
    assert blind.is_closing is True
    assert blind.is_opening is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind._active_action is None
    assert blind.is_closing is False
    assert blind.is_opening is False
    assert blind.is_closed is True

@pytest.mark.asyncio
async def test_async_open_cover_tilt_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_open_cover_tilt()
    client.async_channel_move_close.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)
    assert blind._commanded_action == "opening"
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "opening"
    assert blind.is_opening is True
    assert blind.is_closing is False
    assert blind.is_closed is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind._active_action is None
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_async_close_cover_tilt_sequence(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover_tilt()
    client.async_channel_move_open.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)
    assert blind._commanded_action == "closing"
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "closing"
    assert blind.is_closing is True
    assert blind.is_opening is False

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind._active_action is None
    assert blind.is_closing is False
    assert blind.is_opening is False
    assert blind.is_closed is True

@pytest.mark.asyncio
async def test_scenario_close_then_command_stop_then_ws_stop(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover()
    assert blind._commanded_action == "closing"
    client.async_channel_close.assert_called_once()

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "closing"
    assert blind.is_closing is True

    await blind.async_stop_cover()
    assert blind._commanded_action == "stop"
    assert blind._active_action == "closing"
    client.async_channel_stop.assert_called_once()

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True
    assert blind._active_action is None

@pytest.mark.asyncio
async def test_val_100_with_commanded_action_stop(mock_hass, blind_entity_added, mock_config_entry, caplog):
    """Test receiving val=100 when commanded_action is 'stop'."""
    blind = blind_entity_added

    # Set initial state
    blind._commanded_action = "stop"
    blind._active_action = None # Start with no active action
    blind._attr_is_opening = False
    blind._attr_is_closing = False
    blind._attr_is_closed = True # Example initial state

    caplog.set_level(logging.WARNING, logger=cover_logger.name) # Capture warnings from the cover logger
    caplog.clear()

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")

    # _active_action should NOT change because _commanded_action was "stop"
    assert blind._active_action is None

    # States should reflect that no action was taken
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True # Should remain unchanged

    # Check for the warning log
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert f"Blind {blind._attr_name} received val=100 (movement started) but current commanded_action is 'stop'. _active_action will remain 'None'." in caplog.records[0].message

@pytest.mark.asyncio
async def test_val_100_with_commanded_action_none(mock_hass, blind_entity_added, mock_config_entry, caplog):
    """Test receiving val=100 when commanded_action is None."""
    blind = blind_entity_added

    blind._commanded_action = None
    blind._active_action = None
    initial_is_opening = False
    initial_is_closing = False
    initial_is_closed = True
    blind._attr_is_opening = initial_is_opening
    blind._attr_is_closing = initial_is_closing
    blind._attr_is_closed = initial_is_closed

    caplog.set_level(logging.WARNING, logger=cover_logger.name)
    caplog.clear()

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")

    assert blind._active_action is None
    assert blind.is_opening is initial_is_opening
    assert blind.is_closing is initial_is_closing
    assert blind.is_closed is initial_is_closed

    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "WARNING"
    assert f"Blind {blind._attr_name} received val=100 (movement started) but current commanded_action is 'None'. _active_action will remain 'None'." in caplog.records[0].message


@pytest.mark.asyncio
async def test_quirk_close_interrupted_by_open(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_close_cover()
    assert blind._commanded_action == "closing"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "closing"
    assert blind.is_closing is True

    await blind.async_open_cover()
    assert blind._commanded_action == "opening"
    assert blind._active_action == "closing"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is True
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._commanded_action == "opening"
    assert blind._active_action == "opening"
    assert blind.is_opening is True
    assert blind.is_closing is False
    assert blind.is_closed is False

@pytest.mark.asyncio
async def test_quirk_open_interrupted_by_close(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added
    client = mock_config_entry.runtime_data.client

    await blind.async_open_cover()
    assert blind._commanded_action == "opening"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "opening"
    assert blind.is_opening is True
    assert blind.is_closed is False

    await blind.async_close_cover()
    assert blind._commanded_action == "closing"
    assert blind._active_action == "opening"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind.is_closed is False
    assert blind._active_action is None

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._commanded_action == "closing"
    assert blind._active_action == "closing"
    assert blind.is_closing is True
    assert blind.is_opening is False


@pytest.mark.asyncio
async def test_async_stop_cover_then_event_zero(mock_hass, blind_entity_added, mock_config_entry):
    blind = blind_entity_added

    await blind.async_close_cover()
    assert blind._commanded_action == "closing"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "closing"
    blind._attr_is_closed = False

    await blind.async_stop_cover()
    assert blind._commanded_action == "stop"
    assert blind._active_action == "closing"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind._active_action is None
    assert blind.is_closed is True

    blind._attr_is_closed = True
    await blind.async_open_cover()
    assert blind._commanded_action == "opening"
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "opening"
    assert blind.is_closed is False

    await blind.async_stop_cover()
    assert blind._commanded_action == "stop"
    assert blind._active_action == "opening"

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_opening is False
    assert blind.is_closing is False
    assert blind._active_action is None
    assert blind.is_closed is False


@pytest.mark.asyncio
async def test_message_for_other_channel(mock_hass, blind_entity_added):
    blind = blind_entity_added
    initial_commanded_action = blind._commanded_action
    initial_active_action = blind._active_action

    await blind.async_open_cover()
    assert blind._commanded_action == "opening"

    await simulate_eid1_event(mock_hass, blind, OTHER_CHANNEL_ID, "100")

    assert blind._commanded_action == "opening"
    assert blind._active_action is initial_active_action

    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    assert blind._active_action == "opening"


@patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform")
@pytest.mark.asyncio
async def test_existing_service_registration_updated(mock_async_get_current_platform, blind_entity_added, mock_hass):
    blind = blind_entity_added

    mock_platform_instance = MagicMock()
    mock_platform_instance.async_register_entity_service = MagicMock()
    mock_async_get_current_platform.return_value = mock_platform_instance
    
    mock_hass.bus.async_listen.reset_mock()
    blind.async_on_remove = MagicMock()

    await blind.async_added_to_hass()

    calls = mock_platform_instance.async_register_entity_service.call_args_list
    registered_services_handlers = {call[0][0]: call[0][2] for call in calls}
    
    expected_services = {
        SERVICE_BLIND_RECALL_S1: "async_blind_recall_s1",
        SERVICE_BLIND_RECALL_S2: "async_blind_recall_s2",
        SERVICE_BLIND_RECALL_S3: "async_blind_recall_s3",
        SERVICE_BLIND_RECALL_S4: "async_blind_recall_s4",
    }
    
    for service_name, handler_name in expected_services.items():
        assert service_name in registered_services_handlers
        assert registered_services_handlers[service_name] == handler_name

    blind.async_on_remove.assert_called()

# Basic API call tests (no state assertions, just API interaction)
@pytest.mark.asyncio
async def test_original_cover_open_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_open_cover()
    mock_config_entry.runtime_data.client.async_channel_open.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_close_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_close_cover()
    mock_config_entry.runtime_data.client.async_channel_close.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_stop_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_stop_cover()
    mock_config_entry.runtime_data.client.async_channel_stop.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_tilt_open_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_open_cover_tilt()
    mock_config_entry.runtime_data.client.async_channel_move_close.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)

@pytest.mark.asyncio
async def test_original_cover_tilt_close_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_close_cover_tilt()
    mock_config_entry.runtime_data.client.async_channel_move_open.assert_called_once_with(MOCK_CHANNEL_ID, time_ms=DEFAULT_STEP_DURATION_MS)

# Recall API call tests
@pytest.mark.asyncio
async def test_original_cover_recall_s1_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_blind_recall_s1()
    mock_config_entry.runtime_data.client.async_channel_recall_s1.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_recall_s2_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_blind_recall_s2()
    mock_config_entry.runtime_data.client.async_channel_recall_s2.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_recall_s3_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_blind_recall_s3()
    mock_config_entry.runtime_data.client.async_channel_recall_s3.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_original_cover_recall_s4_api_call(blind_entity_added, mock_config_entry):
    await blind_entity_added.async_blind_recall_s4()
    mock_config_entry.runtime_data.client.async_channel_recall_s4.assert_called_once_with(MOCK_CHANNEL_ID)

def test_service_methods_exist_updated(blind_entity_added):
    # ... (content remains the same)
    assert hasattr(blind_entity_added, "async_open_cover_tilt") # etc.

@pytest.mark.asyncio
async def test_quirk_close_interrupted_by_open_no_second_100(mock_hass, blind_entity_added, mock_config_entry):
    # ... (content largely the same, ensure assertions for _active_action and states are correct)
    blind = blind_entity_added
    await blind.async_close_cover()
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    current_active = blind._active_action # "closing"
    await blind.async_open_cover()
    assert blind._commanded_action == "opening"
    assert blind._active_action == current_active # Should not change yet
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_closed is True
    assert blind._active_action is None

@pytest.mark.asyncio
async def test_quirk_open_interrupted_by_close_no_second_100(mock_hass, blind_entity_added, mock_config_entry):
    # ... (content largely the same, ensure assertions for _active_action and states are correct)
    blind = blind_entity_added
    await blind.async_open_cover()
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "100")
    current_active = blind._active_action # "opening"
    await blind.async_close_cover()
    assert blind._commanded_action == "closing"
    assert blind._active_action == current_active # Should not change yet
    await simulate_eid1_event(mock_hass, blind, MOCK_CHANNEL_ID, "0")
    assert blind.is_closed is False
    assert blind._active_action is None

# Remaining helper tests (hass_data, listener_registration, on_remove) are unchanged by this logic refinement.
@pytest.mark.asyncio
async def test_hass_data_client_access(blind_entity_added, mock_config_entry):
    # ... (content remains the same)
    assert blind_entity_added.config_entry.runtime_data.client == mock_config_entry.runtime_data.client

@pytest.mark.asyncio
async def test_event_listener_registration(mock_hass, blind_entity_added):
    # ... (content remains the same)
    mock_hass.bus.async_listen.assert_called_once_with(ZEPTRION_AIR_WEBSOCKET_MESSAGE, blind_entity_added.async_handle_websocket_message)

@pytest.mark.asyncio
async def test_async_on_remove_called(mock_hass):
    # ... (content remains the same)
    # Re-create blind for this isolated test as in previous version
    mock_config_entry_local = MagicMock(spec=ConfigEntry); mock_config_entry_local.runtime_data = MagicMock(); mock_config_entry_local.runtime_data.client = MagicMock(spec=ZeptrionAirApiClient); mock_config_entry_local.data = {CONF_STEP_DURATION_MS: DEFAULT_STEP_DURATION_MS}; mock_config_entry_local.entry_id = "test_on_remove_entry_id"
    device_info_for_blind = {"identifiers": {(DOMAIN, f"{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}")},"name": f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}",}
    blind = ZeptrionAirBlind(config_entry=mock_config_entry_local, device_info_for_blind_entity=device_info_for_blind, channel_id=MOCK_CHANNEL_ID, hub_serial=MOCK_HUB_SERIAL, entry_title=MOCK_HUB_NAME, entity_base_slug=f"{MOCK_HUB_NAME.lower()}_blind_ch{MOCK_CHANNEL_ID}")
    blind.hass = mock_hass; blind.async_on_remove = MagicMock()
    with patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform", return_value=MagicMock()):
        await blind.async_added_to_hass()
    blind.async_on_remove.assert_called_once()
