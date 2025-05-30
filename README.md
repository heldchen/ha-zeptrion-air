# Home Assistant Zeptrion Air Integration

## Description

This is a custom integration for Home Assistant that allows you to control [Zeptrion Air](https://www.feller.ch/de/Produkte/Gebaeudeautomation/Zeptrion-Systeme/Zeptrion-Air) devices locally over your WLAN. Zeptrion Air hubs connect to your network and expose a REST API for controlling attached lights, blinds, and other devices. This integration aims to bring these devices into Home Assistant for automation and UI control.

## Features

*   **mDNS Discovery:** Automatically discovers Zeptrion Air hubs (devices with hostnames starting `zapp-`) on your local network.
*   **Configuration Flow:** Allows setting up discovered devices and configuring options like step duration for blinds.
*   **Cover Control (Blinds/Markise):**
    *   Full support for Zeptrion channels controlling blinds/shutters (Category 5) and awnings/markise (Category 6).
    *   Standard Home Assistant cover controls: Open, Close, Stop.
    *   Custom services for fine-grained control:
        *   `zeptrion_air.blind_up_step`
        *   `zeptrion_air.blind_down_step`
        *   `zeptrion_air.blind_recall_s1`
        *   `zeptrion_air.blind_recall_s2`
        *   `zeptrion_air.blind_recall_s3`
        *   `zeptrion_air.blind_recall_s4`
*   **Button Entities:** Provides button entities in Home Assistant for each of the custom cover services (Step Up/Down, S1-S4 scenes), making them easily accessible from the UI.
*   **Sensor Entities:** Exposes channel name, group, and Zeptrion icon ID as sensor entities (disabled by default). These can be enabled by the user if desired.
*   **Configurable Step Duration:** The duration (in milliseconds) for the "up step" and "down step" services can be configured via the integration's options flow.

## Current Limitations

*   **Primary Focus on Covers:** While the integration identifies channels for lights (Category 1 - On/Off, Category 3 - Dimmer), Home Assistant `Light` entities for these are not yet implemented. Only cover devices are fully supported with corresponding HA entities.
*   **No Position Feedback for Covers:** The Zeptrion Air API does not provide real-time position feedback for blinds/covers. Therefore, the Home Assistant cover entities will not display the current position (e.g., 50% open). Status updates are optimistic based on commands sent.
*   **Sensors are Static:** The sensor entities for channel name, group, and icon ID are populated once during setup and do not update dynamically if changed on the Zeptrion device itself (though these are typically static).

## Installation

[Add repository to HACS](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=ha-zeptrion-air-integration&owner=alternize)

## Technical Details: API Usage

This integration interacts with the Zeptrion Air hub's local REST API using the following endpoints:

*   **GET `/zrap/id`**: Used to retrieve device identification information, including hardware version, serial number, system type, and software version. This is crucial for device setup and identification.
*   **GET `/zrap/chdes`**: Fetches descriptions for all available channels on the hub. This provides the channel name, assigned group, Zeptrion icon ID, and category (`cat`) which determines the type of device attached (e.g., blind, light).
*   **POST `/zrap/chctrl/ch{X}`** (with URL-encoded `cmd` parameter): Used to send control commands to a specific channel (`ch{X}`).
    *   `cmd=open`: Fully opens the cover.
    *   `cmd=close`: Fully closes the cover.
    *   `cmd=stop`: Stops any ongoing cover movement.
    *   `cmd=move_open_{time_ms}`: Moves the cover up for a specified duration in milliseconds.
    *   `cmd=move_close_{time_ms}`: Moves the cover down for a specified duration in milliseconds.
    *   `cmd=recall_s1` / `recall_s2` / `recall_s3` / `recall_s4`: Recalls a pre-programmed scene (position) for the cover.
    *   *(Note: The API also supports `cmd=on`, `cmd=off`, and `cmd=dim val={Y}` for light channels, which are parsed but not yet fully implemented as HA light entities).*
*   **GET `/zrap/chscan` / `/zrap/chscan/ch{X}`**: While available, this endpoint was found to return `-1` (unknown state) for cover channels and is therefore not currently used for determining cover state.

## Contributing

Contributions to this integration are very welcome! If you have ideas for improvements, new features, or bug fixes, please feel free to:

1.  Open an issue on the GitHub repository to discuss your proposed changes.
2.  Submit a Pull Request with your contributions.

Please try to follow Home Assistant's development guidelines and ensure code is well-tested and documented.

## Disclaimer & License

"Home Assistant" is a project of the Open Home Foundation. This project is not affiliated with nor endorsed by the Open Home Foundation. 

"Zeptrion", "Zeptrion Air" and the Zeptrion Air logo are property of & © by Feller AG 2016. This project is not affiliated with nor endorsed by Feller AG.

All other files in this project are licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
