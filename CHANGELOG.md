# Changelog

All notable changes to this project will be documented in this file.

## [2026.4.0] - 2026-04-10

### Added
- **Reconfigure Flow**: Added support for updating hub hostname/IP via the Home Assistant UI without removing the integration. Includes hardware serial verification for safety.
- **Diagnostics Platform**: Implemented a diagnostics platform to help with troubleshooting by providing redacted system state.
- **Integration Type**: Added `integration_type: hub` to manifest for better classification.
- **Modern Standards**: Full support for Home Assistant 2024+ and 2026 standards.

### Changed
- **Architecture**: Migrated from legacy `hass.data` to modern `entry.runtime_data` for better performance and maintainability.
- **Type Hinting**: Updated codebase to use PEP 695 type aliases for `ConfigEntry`.
- **Options Flow**: Migrated to `OptionsFlowWithReload` for cleaner settings management.
- **Frontend**: Optimized custom card delivery using `register_static_path`. Includes automated migration for existing Lovelace resources and backward compatibility for old URLs.
- **Startup**: Improved startup resilience using `async_config_entry_first_refresh`.
- **Sensors**: Marked Wi-Fi Signal (RSSI) as a diagnostic entity.
- **API**: Switched from deprecated `async_timeout` to native `asyncio.timeout`.

### Fixed
- Fixed an issue where cover tilt timing would ignore user-configured options.
- Resolved potential double-reload cycles during configuration changes.
- Fixed critical missing imports and potential regressions in unique ID generation.
- Corrected `DeviceInfo` regressions to ensure full metadata is available for all devices and channels.

### Dependencies
- Minimum Home Assistant version increased to `2026.4.0`.
- Removed external `async_timeout` dependency.

## [2025.6.1] - Previous Release
- Initial stable release with basic support for Zeptrion Air devices.
