class ZeptrionAirBlindsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }
  
  setConfig(config) {
    
    if (!config.entity) {
      throw new Error('You need to define a cover entity');
    }
    
    this.config = {
      // Default button entity patterns based on your integration - users can override these
      step_up_entity: `${config.entity.replace('cover.', 'button.')}_blind_up_step`,
      step_down_entity: `${config.entity.replace('cover.', 'button.')}_blind_down_step`,
      scene1_entity: `${config.entity.replace('cover.', 'button.')}_blind_recall_s1`,
      scene2_entity: `${config.entity.replace('cover.', 'button.')}_blind_recall_s2`,
      scene3_entity: `${config.entity.replace('cover.', 'button.')}_blind_recall_s3`,
      scene4_entity: `${config.entity.replace('cover.', 'button.')}_blind_recall_s4`,
      ...config
    };
    
    this.render();
  }
  
  set hass(hass) {
    this._hass = hass;
    this.updateCard();
  }
  
  render() {
    
    if (!this.config) {
      this.shadowRoot.innerHTML = '<div>No config set</div>';
      return;
    }
    
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 16px;
        }
        .card-header {
          font-size: 1.2em;
          font-weight: 500;
          margin-bottom: 16px;
          color: var(--primary-text-color);
        }
        .controls-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .button-row {
          display: flex;
          gap: 8px;
          justify-content: center;
        }
        .control-button {
          flex: 1;
          min-height: 44px;
          border: none;
          border-radius: 8px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
        }
        .primary-button {
          background: var(--primary-color);
          color: var(--text-primary-color);
        }
        .primary-button:hover {
          background: var(--primary-color);
          opacity: 0.8;
        }
        .secondary-button {
          background: var(--card-background-color);
          color: var(--primary-text-color);
          border: 1px solid var(--divider-color);
        }
        .secondary-button:hover {
          background: var(--secondary-background-color);
        }
        .scene-button {
          background: var(--accent-color, #ff9800);
          color: white;
        }
        .scene-button:hover {
          background: var(--accent-color, #ff9800);
          opacity: 0.8;
        }
        .step-button {
          background: var(--light-primary-color, #e3f2fd);
          color: var(--primary-color);
          border: 1px solid var(--primary-color);
        }
        .step-button:hover {
          background: var(--primary-color);
          color: var(--text-primary-color);
        }
        .status-info {
          text-align: center;
          margin-bottom: 12px;
          padding: 8px;
          background: var(--secondary-background-color);
          border-radius: 6px;
          font-size: 0.9em;
          color: var(--secondary-text-color);
        }
        ha-icon {
          --mdc-icon-size: 18px;
        }
      </style>
      
      <ha-card>
        <div class="card-header">${this.config.name || 'Zeptrion Air Blinds'}</div>
        <div class="controls-container">
          <div class="status-info">
            <span id="status-text">Loading...</span>
            <div id="button-status" style="font-size: 0.8em; margin-top: 4px;"></div>
          </div>
          
          <!-- Main Controls Row: Up | Step Up | Stop | Step Down | Down -->
          <div class="button-row">
            <button class="control-button primary-button" id="up-btn">
              <ha-icon icon="mdi:arrow-up"></ha-icon> Up
            </button>
            <button class="control-button step-button" id="step-up-btn">
              <ha-icon icon="mdi:arrow-up-bold-outline"></ha-icon> Step Up
            </button>
            <button class="control-button secondary-button" id="stop-btn">
              <ha-icon icon="mdi:stop"></ha-icon> Stop
            </button>
            <button class="control-button step-button" id="step-down-btn">
              <ha-icon icon="mdi:arrow-down-bold-outline"></ha-icon> Step Down
            </button>
            <button class="control-button primary-button" id="down-btn">
              <ha-icon icon="mdi:arrow-down"></ha-icon> Down
            </button>
          </div>
          
          <!-- Scene Controls Row -->
          <div class="button-row">
            <button class="control-button scene-button" id="scene1-btn">Scene 1</button>
            <button class="control-button scene-button" id="scene2-btn">Scene 2</button>
            <button class="control-button scene-button" id="scene3-btn">Scene 3</button>
            <button class="control-button scene-button" id="scene4-btn">Scene 4</button>
          </div>
        </div>
      </ha-card>
    `;

    this.setupEventListeners();
  }

  setupEventListeners() {
    // Standard cover controls
    this.shadowRoot.getElementById('up-btn').addEventListener('click', () => {
      this.callService('cover', 'open_cover');
    });

    this.shadowRoot.getElementById('down-btn').addEventListener('click', () => {
      this.callService('cover', 'close_cover');
    });

    this.shadowRoot.getElementById('stop-btn').addEventListener('click', () => {
      this.callService('cover', 'stop_cover');
    });

    // Custom step controls - call button entities
    this.shadowRoot.getElementById('step-up-btn').addEventListener('click', () => {
      this.pressButton(this.config.step_up_entity);
    });

    this.shadowRoot.getElementById('step-down-btn').addEventListener('click', () => {
      this.pressButton(this.config.step_down_entity);
    });

    // Scene recall buttons - call button entities
    this.shadowRoot.getElementById('scene1-btn').addEventListener('click', () => {
      this.pressButton(this.config.scene1_entity);
    });

    this.shadowRoot.getElementById('scene2-btn').addEventListener('click', () => {
      this.pressButton(this.config.scene2_entity);
    });

    this.shadowRoot.getElementById('scene3-btn').addEventListener('click', () => {
      this.pressButton(this.config.scene3_entity);
    });

    this.shadowRoot.getElementById('scene4-btn').addEventListener('click', () => {
      this.pressButton(this.config.scene4_entity);
    });
  }

  callService(domain, service, data = {}) {
    this._hass.callService(domain, service, {
      entity_id: this.config.entity,
      ...data
    });
  }

  pressButton(entityId) {
    if (!entityId) {
      console.error('Button entity not configured');
      return;
    }
    
    // Check if entity exists
    if (!this._hass.states[entityId]) {
      console.error(`Button entity ${entityId} not found`);
      return;
    }
    console.log(`Pressing button: ${entityId}`);
    this._hass.callService('button', 'press', {
      entity_id: entityId
    });
  }

  updateCard() {
    if (!this._hass || !this.config.entity) return;

    const entity = this._hass.states[this.config.entity];
    if (!entity) {
      this.shadowRoot.getElementById('status-text').textContent = 'Entity not found';
      return;
    }

    const statusText = this.shadowRoot.getElementById('status-text');
    const buttonStatus = this.shadowRoot.getElementById('button-status');
    const state = entity.state;
    const position = entity.attributes.current_position;

    let statusMessage = `State: ${state}`;
    if (position !== undefined) {
      statusMessage += ` | Position: ${position}%`;
    }
    
    statusText.textContent = statusMessage;

    // Check button entity availability
    const buttonEntities = [
      this.config.step_up_entity,
      this.config.step_down_entity,
      this.config.scene1_entity,
      this.config.scene2_entity,
      this.config.scene3_entity,
      this.config.scene4_entity
    ];
    
    const availableButtons = buttonEntities.filter(entityId => 
      entityId && this._hass.states[entityId]
    ).length;
    
    const totalButtons = buttonEntities.filter(entityId => entityId).length;
    
    if (totalButtons > 0) {
      buttonStatus.textContent = `Button entities: ${availableButtons}/${totalButtons} available`;
    }
  }
  
  getCardSize() {
    return 3;
  }
  
  static getConfigElement() {
    return document.createElement('zeptrion-air-blinds-card-editor');
  }
  
  static getStubConfig() {
    return {
      entity: 'cover.zeptrion_air_blinds',
      name: 'Zeptrion Air Blinds'
    };
  }
}

// Configuration editor
class ZeptrionAirBlindsCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = config;
    this.render();
  }

  render() {
    this.innerHTML = `
      <div style="padding: 16px;">
        <label style="display: block; margin-bottom: 8px;">Cover Entity:</label>
        <input type="text" id="entity" value="${this.config.entity || ''}" 
               style="width: 100%; margin-bottom: 16px; padding: 8px;" />
        
        <label style="display: block; margin-bottom: 8px;">Name:</label>
        <input type="text" id="name" value="${this.config.name || ''}" 
               style="width: 100%; margin-bottom: 16px; padding: 8px;" />
        
        <details style="margin-bottom: 16px;">
          <summary style="cursor: pointer; font-weight: bold;">Button Entity Configuration</summary>
          <div style="margin-top: 8px;">
            <p style="font-size: 0.9em; color: #666; margin-bottom: 12px;">
              Button entities are auto-detected based on cover entity name. Override if needed:
            </p>
            
            <label style="display: block; margin-bottom: 4px;">Step Up Button:</label>
            <input type="text" id="step_up_entity" value="${this.config.step_up_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
            
            <label style="display: block; margin-bottom: 4px;">Step Down Button:</label>
            <input type="text" id="step_down_entity" value="${this.config.step_down_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
            
            <label style="display: block; margin-bottom: 4px;">Scene 1 Button:</label>
            <input type="text" id="scene1_entity" value="${this.config.scene1_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
            
            <label style="display: block; margin-bottom: 4px;">Scene 2 Button:</label>
            <input type="text" id="scene2_entity" value="${this.config.scene2_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
            
            <label style="display: block; margin-bottom: 4px;">Scene 3 Button:</label>
            <input type="text" id="scene3_entity" value="${this.config.scene3_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
            
            <label style="display: block; margin-bottom: 4px;">Scene 4 Button:</label>
            <input type="text" id="scene4_entity" value="${this.config.scene4_entity || ''}" 
                   style="width: 100%; margin-bottom: 8px; padding: 6px;" />
          </div>
        </details>
      </div>
    `;

    this.addEventListener('input', this.configChanged);
  }

  configChanged(ev) {
    const config = {
      ...this.config,
      [ev.target.id]: ev.target.value
    };
    
    const event = new CustomEvent('config-changed', {
      detail: { config },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
}

customElements.define('zeptrion-air-blinds-card', ZeptrionAirBlindsCard);
customElements.define('zeptrion-air-blinds-card-editor', ZeptrionAirBlindsCardEditor);

// Register the card
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'zeptrion-air-blinds-card',
  name: 'Zeptrion Air Blinds Card',
  description: 'A card for controlling Zeptrion Air blinds with custom actions'
});
