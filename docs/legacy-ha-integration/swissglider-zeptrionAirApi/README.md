## Zeptrion Air

This are the Classes to use the Zeptrion Air Lights etc. Zeptrion Air is
a product from Feller. Zeptrion Air Panel are switches for Light, Blinds
etc. A panel can have up to 8 switches. Each of this switches are called
Button.

### 1) Hub

The ZeptrionAir Hub handles all the ZeptrionAir Panel. The Hub is
searching (browse) the panels with mDNS (zeroconf). If panels are found
with mDNS the Hub is requesting the panels for all additional needed
informations

### 2) Panel

Panel is the panel that can have up to 8 buttons (Switches)

### 3) Button

The Button is on of the button that are hold on a Panel A
Button is Switch for example for a Light or Blinds etc. With the
Button Class you can read the status and control the device
Button Status is handled with websocket and is implemented with asyncio

### Python compatibility
Only working with Python 3.6 and above

### Sample to use it:

``` python
import asyncio
import time
import json
from zeptrion_air_api import Hub

async def do_close(hub):
    """Close the System."""
    await hub.close()

def press_info_handler(press_info):
    """Handle if the button is pressed."""
    print(press_info)

def found_new_panels(panel):
    """Handle if a new Zeptrion Air Panel is found."""
    for button in panel.all_buttons:
        if button:
            button.listen_to(press_info_handler)

if __name__ == '__main__':
    """Init the main test."""
    loop = asyncio.get_event_loop()
    za_hub = Hub(loop, found_new_panels)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Unregistering...")
        loop.run_until_complete(do_close(za_hub))
    finally:
        loop.close()
```

### Class Diagram
![..](http://www.plantuml.com/plantuml/proxy?src=https://raw.githubusercontent.com/swissglider/zeptrionAirApi/master/class-diagram.wsd)

### Sequence Diagram (example/async_server.py)
![..](http://www.plantuml.com/plantuml/proxy?src=https://raw.githubusercontent.com/swissglider/zeptrionAirApi/master/sequence-diagram.wsd)
