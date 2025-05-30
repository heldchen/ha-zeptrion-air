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
        .card-header {
          font-weight: 500;
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
        .tilt-button {
          background: var(--light-primary-color, #e3f2fd);
          color: var(--primary-color);
          border: 1px solid var(--primary-color);
        }
        .tilt-button:hover {
          background: var(--primary-color);
          color: var(--text-primary-color);
        }
      </style>
      
      <ha-card>
        <div class="card-header"><div class="name">${this.config.name || 'Zeptrion Air Blinds'}</div></div>
        <div class="controls-container">
          <div class="button-row">
            <button class="control-button primary-button" id="up-btn">
              <ha-icon icon="mdi:arrow-up-bold"></ha-icon>
            </button>
            <button class="control-button tilt-button" id="tilt-open-btn">
              <ha-icon icon="mdi:arrow-up-thin"></ha-icon>
            </button>
            <button class="control-button secondary-button" id="stop-btn">
              <ha-icon icon="mdi:stop"></ha-icon>
            </button>
            <button class="control-button tilt-button" id="tilt-close-btn">
              <ha-icon icon="mdi:arrow-down-thin"></ha-icon>
            </button>
            <button class="control-button primary-button" id="down-btn">
              <ha-icon icon="mdi:arrow-down-bold"></ha-icon>
            </button>
          </div>
          
          <div class="button-row">
            <button class="control-button scene-button" id="scene1-btn"><ha-icon icon="mdi:numeric-1-box-outline"></ha-icon></button>
            <button class="control-button scene-button" id="scene2-btn"><ha-icon icon="mdi:numeric-2-box-outline"></ha-icon></button>
            <button class="control-button scene-button" id="scene3-btn"><ha-icon icon="mdi:numeric-3-box-outline"></ha-icon></button>
            <button class="control-button scene-button" id="scene4-btn"><ha-icon icon="mdi:numeric-4-box-outline"></ha-icon></button>
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
    this.shadowRoot.getElementById('tilt-open-btn').addEventListener('click', () => {
      this.callService('cover', 'open_cover_tilt');
    });

    this.shadowRoot.getElementById('tilt-close-btn').addEventListener('click', () => {
      this.callService('cover', 'close_cover_tilt');
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
    // do nothing for now
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
