import asyncio
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_PATH = ROOT / "custom_components" / "zeptrion_air" / "frontend.py"


def _install_stubs() -> None:
    # homeassistant stubs used by frontend.py
    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    frontend = types.ModuleType("homeassistant.components.frontend")
    http = types.ModuleType("homeassistant.components.http")
    helpers = types.ModuleType("homeassistant.helpers")
    event = types.ModuleType("homeassistant.helpers.event")

    @dataclass
    class StaticPathConfig:
        url_path: str
        path: str
        cache_headers: bool

    def add_extra_js_url(hass, url):
        hass._added_js_urls.append(url)

    def async_call_later(hass, delay, callback):
        hass._scheduled = (delay, callback)

    frontend.add_extra_js_url = add_extra_js_url
    http.StaticPathConfig = StaticPathConfig
    event.async_call_later = async_call_later

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.components"] = components
    sys.modules["homeassistant.components.frontend"] = frontend
    sys.modules["homeassistant.components.http"] = http
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.event"] = event

    # package + const stub for relative import from .const
    custom_components = types.ModuleType("custom_components")
    zep_pkg = types.ModuleType("custom_components.zeptrion_air")
    zep_pkg.__path__ = []
    const_mod = types.ModuleType("custom_components.zeptrion_air.const")
    const_mod.DOMAIN = "zeptrion_air"

    sys.modules["custom_components"] = custom_components
    sys.modules["custom_components.zeptrion_air"] = zep_pkg
    sys.modules["custom_components.zeptrion_air.const"] = const_mod


def _load_frontend_module():
    _install_stubs()
    module_name = "custom_components.zeptrion_air.frontend"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, FRONTEND_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FakeHTTP:
    def __init__(self):
        self.calls = []

    async def async_register_static_paths(self, paths):
        self.calls.append(paths)


class _FakeBus:
    def __init__(self):
        self.events = []

    def async_fire(self, event_type):
        self.events.append(event_type)


class _FakeResources:
    def __init__(self):
        self.data = {}
        self.created = []
        self.deleted = []

    async def async_create_item(self, item):
        self.created.append(item)

    async def async_delete_item(self, resource_id):
        self.deleted.append(resource_id)


class _FakeLovelace:
    def __init__(self):
        self.resources = _FakeResources()


class _FakeHass:
    def __init__(self):
        self.http = _FakeHTTP()
        self.bus = _FakeBus()
        self.data = {"lovelace": _FakeLovelace()}
        self._added_js_urls = []
        self._scheduled = None


def test_setup_registers_new_and_legacy_static_paths():
    frontend_module = _load_frontend_module()
    hass = _FakeHass()
    asyncio.run(frontend_module.async_setup_frontend(hass, None))

    assert len(hass.http.calls) == 1
    paths = hass.http.calls[0]
    assert paths[0].url_path == "/zeptrion_air/zeptrion-air-blinds-card.js"
    assert paths[1].url_path == "/api/zeptrion_air/zeptrion-air-blinds-card.js"


def test_setup_is_idempotent():
    frontend_module = _load_frontend_module()
    hass = _FakeHass()

    asyncio.run(frontend_module.async_setup_frontend(hass, None))
    asyncio.run(frontend_module.async_setup_frontend(hass, None))

    assert len(hass.http.calls) == 1


def test_delayed_setup_migrates_legacy_resource():
    frontend_module = _load_frontend_module()
    hass = _FakeHass()
    resources = hass.data["lovelace"].resources
    resources.data = {"old_id": {"url": "/api/zeptrion_air/zeptrion-air-blinds-card.js"}}

    asyncio.run(frontend_module.async_setup_frontend(hass, None))

    delay, callback = hass._scheduled
    assert delay == 5
    asyncio.run(callback(None))

    assert "/zeptrion_air/zeptrion-air-blinds-card.js" in hass._added_js_urls
    assert resources.deleted == ["old_id"]
    assert resources.created == [{"url": "/zeptrion_air/zeptrion-air-blinds-card.js", "type": "module"}]
    assert "frontend_reload" in hass.bus.events
