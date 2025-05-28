# Conceptual Outline: `zeptrion-air-blinds-card.js`

This document provides a conceptual outline for a custom Home Assistant Lovelace card designed to control Zeptrion Air blinds. It is intended as a starting point for a frontend developer familiar with JavaScript, LitElement, and Home Assistant custom card development.

## 1. Card Name and Registration (Conceptual)

*   **Class Name:** `ZeptrionAirBlindsCard` (extends `LitElement` or a base Home Assistant card class like `HaCard`)
*   **Custom Element Tag:** `customElements.define('zeptrion-air-blinds-card', ZeptrionAirBlindsCard);`
*   **Static `getStubConfig()`:** Could return a basic config: `{ entity: "cover.my_zeptrion_blind" }`

## 2. Configuration (`setConfig(config)`)

The card would primarily need the `entity_id` of the Zeptrion Air cover entity.

*   `config.entity`: (String, required) The entity ID of the `cover` entity (e.g., `cover.zapp_12345_ch1_blinds`).
    *   Error handling if `entity` is not provided or is not a cover entity.

## 3. Properties

The LitElement would define properties to hold its state and configuration:

*   `hass`: (Object) The Home Assistant `hass` object, passed down by Lovelace. Used to get states and call services.
*   `config`: (Object) The card configuration object stored from `setConfig`.
*   `stateObj`: (Object) The state object of the configured cover entity, derived from `hass.states[config.entity]`.

## 4. HTML Structure (Conceptual - within `render()` method)

The card would aim for a layout similar to standard entity cards, with additional rows for the custom buttons.

```html
<ha-card header="[Friendly Name of Cover Entity]">
  <div class="card-content">
    <!-- Standard Cover Controls -->
    <div class="cover-controls standard-row">
      <ha-icon-button icon="hass:arrow-up" title="Open" @click="${this._callOpenService}"></ha-icon-button>
      <ha-icon-button icon="hass:stop" title="Stop" @click="${this._callStopService}"></ha-icon-button>
      <ha-icon-button icon="hass:arrow-down" title="Close" @click="${this._callCloseService}"></ha-icon-button>
    </div>

    <!-- Zeptrion Step Controls -->
    <div class="cover-controls zeptrion-step-row">
      <ha-icon-button icon="mdi:chevron-up" title="Step Up" @click="${this._callService('blind_up_step')}"></ha-icon-button>
      <span>Step</span>
      <ha-icon-button icon="mdi:chevron-down" title="Step Down" @click="${this._callService('blind_down_step')}"></ha-icon-button>
    </div>

    <!-- Zeptrion Scene Controls (Example for S1, S2) -->
    <div class="cover-controls zeptrion-scene-row">
      <mwc-button dense outlined @click="${this._callService('blind_recall_s1')}">S1</mwc-button>
      <mwc-button dense outlined @click="${this._callService('blind_recall_s2')}">S2</mwc-button>
      <!-- Repeat for S3, S4 -->
    </div>
    <div class="cover-controls zeptrion-scene-row">
      <mwc-button dense outlined @click="${this._callService('blind_recall_s3')}">S3</mwc-button>
      <mwc-button dense outlined @click="${this._callService('blind_recall_s4')}">S4</mwc-button>
    </div>
  </div>
</ha-card>
```

*   `ha-card`: Standard container. Header could be dynamic based on entity's friendly name.
*   `ha-icon-button`: For standard up/stop/down and step controls.
*   `mwc-button`: Material Web Component button, often used in HA for scene-like actions. `dense` and `outlined` for styling.
*   Click handlers (`@click`) would call internal methods.

## 5. State Handling and Display

*   The `render()` method would re-render when `hass` or `config` changes.
*   `this.stateObj = this.hass.states[this.config.entity];` would get the current state.
*   The card could display the entity's name: `this.stateObj.attributes.friendly_name`.
*   Button availability:
    *   Standard Open/Close/Stop buttons could be disabled based on `this.stateObj.state` (e.g., disable "Open" if already open), though Zeptrion covers don't report state reliably. For simplicity, they might always be enabled.
    *   Custom service buttons (Step, Scenes) are typically always enabled as they are stateless commands.

## 6. Service Calls (JavaScript methods)

Methods would be defined to call the relevant services.

*   `_callOpenService()`: Calls `cover.open_cover` for `this.config.entity`.
*   `_callCloseService()`: Calls `cover.close_cover`.
*   `_callStopService()`: Calls `cover.stop_cover`.

*   `_callService(serviceName)`: A generic helper method for Zeptrion services.
    ```javascript
    _callService(serviceName) {
      this.hass.callService('zeptrion_air', serviceName, {
        entity_id: this.config.entity
      });
    }
    ```
    This method would be called by the custom buttons:
    *   Step Up: `this._callService('blind_up_step')`
    *   Step Down: `this._callService('blind_down_step')`
    *   Recall S1: `this._callService('blind_recall_s1')`
    *   ...and so on for S2, S3, S4.

## 7. Styling (CSS - within `static get styles()`)

*   CSS would be defined using LitElement's `static get styles()` method with `css\`...\``.
*   Styles would be needed for:
    *   Arranging buttons in rows.
    *   Spacing.
    *   Ensuring consistency with Home Assistant theme variables if possible.

## 8. Example Usage in Lovelace (YAML)

```yaml
type: custom:zeptrion-air-blinds-card
entity: cover.your_zeptrion_blind_entity_id
```

## Disclaimer

This is a conceptual guide. Actual implementation would require proficiency in JavaScript, LitElement, and the Home Assistant frontend development environment. Error handling, more advanced state management, and detailed styling are not covered here.
