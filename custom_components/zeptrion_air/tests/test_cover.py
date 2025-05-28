import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.cover import CoverEntityFeature
# from homeassistant.const import Platform # Not directly used, DOMAIN from const is better for identifiers
from homeassistant.helpers.entity_platform import async_get_current_platform


from custom_components.zeptrion_air.cover import ZeptrionAirBlind
from custom_components.zeptrion_air.api import ZeptrionAirApiClient
from custom_components.zeptrion_air.const import (
    DOMAIN, # Added DOMAIN for identifiers
    SERVICE_BLIND_UP_STEP,
    SERVICE_BLIND_DOWN_STEP,
    SERVICE_BLIND_RECALL_S1,
    SERVICE_BLIND_RECALL_S2, # Added missing import from prompt
    SERVICE_BLIND_RECALL_S3, # Added missing import from prompt
    SERVICE_BLIND_RECALL_S4  # Added missing import from prompt
)

MOCK_HUB_SERIAL = "ZAPP12345"
MOCK_HUB_NAME = "Zeptrion Hub"
MOCK_CHANNEL_ID = 1

@pytest.fixture
def mock_api_client():
    client = MagicMock(spec=ZeptrionAirApiClient)
    client.async_channel_open = AsyncMock()
    client.async_channel_close = AsyncMock()
    client.async_channel_stop = AsyncMock()
    client.async_channel_move_open = AsyncMock()
    client.async_channel_move_close = AsyncMock()
    client.async_channel_recall_s1 = AsyncMock()
    client.async_channel_recall_s2 = AsyncMock() # Added mock for S2
    client.async_channel_recall_s3 = AsyncMock() # Added mock for S3
    client.async_channel_recall_s4 = AsyncMock() # Added mock for S4
    return client

@pytest.fixture
def blind_entity(mock_api_client):
    # Simplified device_info for the blind itself
    device_info_for_blind = {
        "identifiers": {(DOMAIN, f"{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}")}, # Corrected to use DOMAIN and match structure
        "name": f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}", # Adjusted name to match cover.py
        "via_device": (DOMAIN, MOCK_HUB_SERIAL),
    }
    return ZeptrionAirBlind(
        api_client=mock_api_client,
        device_info_for_blind_entity=device_info_for_blind,
        channel_id=MOCK_CHANNEL_ID,
        hub_serial=MOCK_HUB_SERIAL,
        entry_title=MOCK_HUB_NAME # entry_title is hub's name
    )

def test_cover_initial_state(blind_entity):
    assert blind_entity.name == f"{MOCK_HUB_NAME} Blind Ch{MOCK_CHANNEL_ID}" # Adjusted expected name
    assert blind_entity.unique_id == f"{MOCK_HUB_SERIAL}_ch{MOCK_CHANNEL_ID}_cover"
    assert blind_entity.is_closed is None 
    assert not blind_entity.is_opening
    assert not blind_entity.is_closing
    assert blind_entity.current_cover_position is None
    assert blind_entity.supported_features == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

@pytest.mark.asyncio
async def test_cover_open(blind_entity, mock_api_client):
    await blind_entity.async_open_cover()
    mock_api_client.async_channel_open.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_close(blind_entity, mock_api_client):
    await blind_entity.async_close_cover()
    mock_api_client.async_channel_close.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_stop(blind_entity, mock_api_client):
    await blind_entity.async_stop_cover()
    mock_api_client.async_channel_stop.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_up_step(blind_entity, mock_api_client):
    await blind_entity.async_blind_up_step()
    mock_api_client.async_channel_move_open.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_down_step(blind_entity, mock_api_client): # Added test from prompt
    await blind_entity.async_blind_down_step()
    mock_api_client.async_channel_move_close.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_recall_s1(blind_entity, mock_api_client):
    await blind_entity.async_blind_recall_s1()
    mock_api_client.async_channel_recall_s1.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_recall_s2(blind_entity, mock_api_client): # Added test
    await blind_entity.async_blind_recall_s2()
    mock_api_client.async_channel_recall_s2.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_recall_s3(blind_entity, mock_api_client): # Added test
    await blind_entity.async_blind_recall_s3()
    mock_api_client.async_channel_recall_s3.assert_called_once_with(MOCK_CHANNEL_ID)

@pytest.mark.asyncio
async def test_cover_blind_recall_s4(blind_entity, mock_api_client): # Added test
    await blind_entity.async_blind_recall_s4()
    mock_api_client.async_channel_recall_s4.assert_called_once_with(MOCK_CHANNEL_ID)

def test_service_methods_exist(blind_entity):
    assert hasattr(blind_entity, "async_blind_up_step")
    assert hasattr(blind_entity, "async_blind_down_step")
    assert hasattr(blind_entity, "async_blind_recall_s1")
    assert hasattr(blind_entity, "async_blind_recall_s2") # Added check
    assert hasattr(blind_entity, "async_blind_recall_s3") # Added check
    assert hasattr(blind_entity, "async_blind_recall_s4") # Added check


@patch("custom_components.zeptrion_air.cover.entity_platform.async_get_current_platform")
@pytest.mark.asyncio
async def test_service_registration(mock_async_get_current_platform, blind_entity):
    mock_platform = MagicMock()
    mock_platform.async_register_entity_service = MagicMock()
    mock_async_get_current_platform.return_value = mock_platform
    
    # Simulate Home Assistant environment calling this method
    # In a real HA setup, this is called by HA after the entity is added.
    # For testing, we call it directly.
    await blind_entity.async_added_to_hass()
    
    calls = mock_platform.async_register_entity_service.call_args_list
    registered_services_handlers = {call[0][0]: call[0][2] for call in calls} # service_name: handler_method_name_str
    
    expected_services = {
        SERVICE_BLIND_UP_STEP: "async_blind_up_step",
        SERVICE_BLIND_DOWN_STEP: "async_blind_down_step",
        SERVICE_BLIND_RECALL_S1: "async_blind_recall_s1",
        SERVICE_BLIND_RECALL_S2: "async_blind_recall_s2",
        SERVICE_BLIND_RECALL_S3: "async_blind_recall_s3",
        SERVICE_BLIND_RECALL_S4: "async_blind_recall_s4",
    }
    
    for service_name, handler_name in expected_services.items():
        assert service_name in registered_services_handlers
        assert registered_services_handlers[service_name] == handler_name
