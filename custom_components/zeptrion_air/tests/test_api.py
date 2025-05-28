import pytest
import aiohttp
from unittest.mock import AsyncMock, patch, MagicMock

from custom_components.zeptrion_air.api import ZeptrionAirApiClient, ZeptrionAirApiClientCommunicationError
from custom_components.zeptrion_air.const import CONF_HOSTNAME

MOCK_HOSTNAME = "fakehost.local"

@pytest.fixture
def mock_session():
    session = MagicMock(spec=aiohttp.ClientSession)
    session.request = AsyncMock()
    return session

@pytest.mark.asyncio
async def test_api_client_creation(mock_session):
    client = ZeptrionAirApiClient(hostname=MOCK_HOSTNAME, session=mock_session)
    assert client._hostname == MOCK_HOSTNAME
    assert client._baseurl == f"http://{MOCK_HOSTNAME}"

@pytest.mark.asyncio
async def test_get_channel_scan_info(mock_session):
    client = ZeptrionAirApiClient(hostname=MOCK_HOSTNAME, session=mock_session)
    channel_id = 1
    expected_url = f"http://{MOCK_HOSTNAME}/zrap/chscan/ch{channel_id}"
    
    # Mock XML response
    mock_response_text = "<zrap><chscan><ch id='1'><val>-1</val></ch></chscan></zrap>"
    mock_session.request.return_value.__aenter__.return_value.text = AsyncMock(return_value=mock_response_text)
    mock_session.request.return_value.__aenter__.return_value.status = 200
    
    # Patch xmltodict.parse
    with patch("custom_components.zeptrion_air.api.xmltodict.parse") as mock_parse:
        mock_parse.return_value = {"zrap": {"chscan": {"ch": {"@id": "1", "val": "-1"}}}}
        result = await client.async_get_channel_scan_info(channel_id)
        
        mock_session.request.assert_called_once_with(
            method="get",
            url=expected_url,
            headers=None,
            data=None,
        )
        mock_parse.assert_called_once_with(mock_response_text)
        assert result == {"zrap": {"chscan": {"ch": {"@id": "1", "val": "-1"}}}}

@pytest.mark.asyncio
async def test_channel_open(mock_session):
    client = ZeptrionAirApiClient(hostname=MOCK_HOSTNAME, session=mock_session)
    channel_id = 2
    expected_url = f"http://{MOCK_HOSTNAME}/zrap/chctrl/ch{channel_id}"
    expected_data = {"cmd": "open"}

    # Mock response for POST (often empty or redirect for control commands)
    mock_session.request.return_value.__aenter__.return_value.text = AsyncMock(return_value="") # Or some minimal XML if API returns it
    mock_session.request.return_value.__aenter__.return_value.status = 200 # Or 302 then 200 for actual device

    with patch("custom_components.zeptrion_air.api.urlencode") as mock_urlencode, \
         patch("custom_components.zeptrion_air.api.xmltodict.parse") as mock_parse:
        mock_urlencode.return_value = "cmd=open" # Expected encoded string
        # Simulate that empty response leads to empty dict by the wrapper
        mock_parse.return_value = {} # Adjust if wrapper returns something else for empty text

        result = await client.async_channel_open(channel_id)

        mock_session.request.assert_called_once_with(
            method="post",
            url=expected_url,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data="cmd=open" 
        )
        mock_urlencode.assert_called_once_with(expected_data)
        # The wrapper returns {} for empty response from xmltodict.parse if text is empty
        assert result == {} 

@pytest.mark.asyncio
async def test_channel_move_open_timed(mock_session):
    client = ZeptrionAirApiClient(hostname=MOCK_HOSTNAME, session=mock_session)
    channel_id = 3
    time_ms = 750
    expected_cmd = f"move_open_{time_ms}"
    expected_data_dict = {"cmd": expected_cmd}
    
    mock_session.request.return_value.__aenter__.return_value.text = AsyncMock(return_value="")
    mock_session.request.return_value.__aenter__.return_value.status = 200

    with patch("custom_components.zeptrion_air.api.urlencode") as mock_urlencode, \
         patch("custom_components.zeptrion_air.api.xmltodict.parse") as mock_parse:
        mock_urlencode.return_value = f"cmd={expected_cmd}"
        mock_parse.return_value = {} # Simulate empty dict for empty response

        result = await client.async_channel_move_open(channel_id, time_ms=time_ms)

        mock_urlencode.assert_called_once_with(expected_data_dict)
        # Check that the data argument in session.request call matches the urlencoded string
        called_args, called_kwargs = mock_session.request.call_args
        assert called_kwargs.get('data') == f"cmd={expected_cmd}"
        assert result == {}

# Add similar tests for:
# async_get_all_channels_scan_info
# async_channel_close
# async_channel_stop
# async_channel_move_close (default and timed)
# async_channel_recall_s1 (and other scenes)
# Test communication error exception

@pytest.mark.asyncio
async def test_api_communication_error(mock_session):
    client = ZeptrionAirApiClient(hostname=MOCK_HOSTNAME, session=mock_session)
    mock_session.request.side_effect = aiohttp.ClientError("Test communication error")
    
    with pytest.raises(ZeptrionAirApiClientCommunicationError):
        await client.async_get_channel_scan_info(1)
