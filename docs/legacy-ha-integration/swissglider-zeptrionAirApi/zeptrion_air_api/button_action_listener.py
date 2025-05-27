"""
Support for zeptrion_air_api.button_action_listener.

For more details about this Class, please refer to the documentation at
https://github.com/swissglider/zeptrionAirApi
"""

import time
import json
import asyncio
import websockets


class ButtonActionListenerHandler():
    """
    This is the Button Action Listener Handler.

    This is the only class to be used from this module

    """

    def __init__(self, loop):
        """Initialize the ButtonActionListenerHandler."""
        self.loop = loop
        self.button_action_listener = []
        self.to_finish = False
        self.finished = False
        loop.create_task(self.init())

    async def init(self):
        """Initialize the async part of ButtonActionListenerHandler."""
        while not self.to_finish:
            await asyncio.sleep(0)
        self.finished = True
        return 'finished'

    async def close(self):
        """Close the ButtonActionListenerHandler."""
        self.to_finish = True
        while self.finished:
            await asyncio.sleep(0)
        for listener in self.button_action_listener:
            listener['listener'].close()
            try:
                if not listener['task'].done():
                    listener['task'].cancel()
            except asyncio.CancelledError:
                pass

    def register_new_listener(self, panel, button_pressed_handler):
        """Register a new listener."""
        btn = ButtonActionListener(panel)
        btn_task = self.loop.create_task(
            btn.message_hanlder(button_pressed_handler)
        )
        self.button_action_listener.append({
            'listener': btn,
            'task': btn_task,
        })


class ButtonActionListener():
    """
    This is the Listener for all zeptrion devices if they are pressed.

    This is only for internal use
    """

    def __init__(self, panel):
        """Initialize the ButtonActionListener."""
        self._ip = panel.ip
        self.port = panel.port
        self.websocket = None

    async def message_hanlder(self, message_handler):
        """
        Wait for and handle messages.

        This, when from the ZeptrionAir when Button is pressed.
        """
        if self.websocket:
            return False
        url = 'ws://' + self._ip + ':' + str(self.port)
        async with websockets.connect(url) as websocket:
            self.websocket = websocket

            async for message in websocket:
                status_time = time.time()
                press_info = await self.get_press_info(message, status_time)
                if press_info is not None:
                    message_handler(press_info)

    async def get_press_info(self, new_message, status_time):
        # pylint: disable=too-many-return-statements
        """Handle the message and convert it into a Press Info."""
        if not new_message:
            return None
        msg1 = Message(new_message, self._ip, self.port, status_time)
        if not msg1 or not msg1.eid:
            return None
        # manage value typed press
        # ------------------------
        # only pressed/released are managed from smart button
        if msg1.eid == 'eid2' and msg1.button_nr > 3:
            return None
        if msg1.eid == 'eid2' and msg1.button_nr == -1:
            return None
        # if value typed return value typed
        if msg1.eid == 'eid1':
            return PressInfo(value_msg=msg1)
        # manage second press
        # --------------------------------
        message2 = await self.websocket.recv()
        msg2 = Message(message2, self._ip, self.port, time.time())
        if not msg2 or not msg2.eid:
            return None
        if msg2.eid == 'eid2' and not msg2.button_nr == -1:
            return None
        if msg2.eid == 'eid1':
            return PressInfo(value_msg=msg2)
        return PressInfo(
            status_msg1=msg1,
            status_msg2=msg2
        )

    def close(self):
        """Close the ButtonActionListener."""
        self.websocket.close()

    @property
    def ip(self):  # pylint: disable=invalid-name
        """Return the ip."""
        return self._ip


class PressInfo():
    """
    This is the PressInfo.

    The pressInfo will be returned to the client.
    It content a PressInfo after button has been pressed with:
    - ip
    - port
    - type (value, single_pressed, long_pressed)
    - channel / button_nr
    - value
    - status_update_time
    """

    def __init__(
            self, value_msg=None, status_msg1=None,
            status_msg2=None, status_msg3=None
    ):
        """Initialize the PressInfo."""
        self._ip = None
        self._port = None
        self.type = None
        self.channel = None
        self.button_nr = None
        self.value = None
        if value_msg is not None:
            self.status_update_time = value_msg.status_time
            self._ip = value_msg.ip
            self._port = value_msg.ip
            self.channel = value_msg.channel
            self.value = value_msg.value
            self.type = 'value'
            if self.channel == 1:
                self.button_nr = 4
            if self.channel == 2:
                self.button_nr = 6
        elif status_msg1 is not None:
            self.status_update_time = status_msg1.status_time
            self._ip = status_msg1.ip
            self._port = status_msg1.ip
            self.button_nr = status_msg1.button_nr
            compare_time = status_msg2.status_time - status_msg1.status_time
            if status_msg3:
                self.type = 'dubble_pressed'
            elif compare_time < 1.0:
                self.type = 'single_pressed'
            else:
                self.type = 'long_pressed'

    def __repr__(self):
        """Return a String representing the ZeptrionAirPanel."""
        return_string = "IP/Port: " + str(self._ip) + ':' + str(self._port)
        if self.type == 'value':
            return_string += "\tChannel: " + str(self.channel)
            return_string += "\tType: " + str(self.type)
            return_string += "\tValue: " + str(self.value)
        else:
            return_string += "\tButton: " + str(self.button_nr)
            return_string += "\tType: " + str(self.type)
        return return_string

    @property
    def ip(self):  # pylint: disable=invalid-name
        """Return the ip."""
        return self._ip

    @property
    def port(self):
        """Return the port."""
        return self._port


class Message():
    """
    Encrypt the message from the Zeptrion Air Button.

    This is only for internal use

    """

    def __init__(self, message, ip, port, status_time):
        """Initialize the PressInfo."""
        try:
            message = json.loads(message)
        except ValueError as exc:
            raise exc
        else:
            self.message = message
            self._ip = ip
            self._port = port
            self.status_time = status_time
            self.channel = None
            if message and 'eid1' in message:
                self.channel = message['eid1']['ch']
                if self.channel == 1:
                    self.button_nr = 4
                if self.channel == 2:
                    self.button_nr = 6
            if message and 'eid2' in message:
                bta = message['eid2']['bta']
                buttons = bta.split('.')
                try:
                    self.button_nr = buttons.index('P')
                except ValueError:
                    self.button_nr = -1

    @property
    def ip(self):  # pylint: disable=invalid-name
        """Return the ip."""
        return self._ip

    @property
    def port(self):
        """Return the port."""
        return self._port

    @property
    def eid(self):
        """Return the eid."""
        if self.message and 'eid1' in self.message:
            return 'eid1'
        if self.message and 'eid2' in self.message:
            return 'eid2'
        return None

    @property
    def bta(self):
        """Return the bta."""
        if self.message and 'eid2' in self.message:
            return self.message['eid2']['bta']
        return None

    @property
    def value(self):
        """Return the bta."""
        if self.message and 'eid1' in self.message:
            return self.message['eid1']['val']
        return None
