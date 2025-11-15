"""Walking Pad Api."""

import asyncio
import logging
from enum import Enum, unique

from bleak import BleakError
from bleak.backends.device import BLEDevice
from ph4_walkingpad.pad import Controller, WalkingPadCurStatus

from .const import BeltState, WalkingPadMode, WalkingPadStatus

_LOGGER = logging.getLogger(__name__)


@unique
class WalkingPadConnectionStatus(Enum):
    """An enumeration of the possible connection states."""

    NOT_CONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


class WalkingPad:
    """The WalkingPad device."""

    def __init__(self, name: str, ble_device: BLEDevice) -> None:
        """Create a WalkingPad object."""

        self._name = name
        self._ble_device = ble_device
        self._controller = Controller()
        self._controller.log_messages_info = False
        self._callbacks = []
        self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
        self._register_controller_callbacks()

    def _register_controller_callbacks(self):
        self._controller.handler_cur_status = self._on_status_update

    def _begin_cmd(self) -> asyncio.Lock:
        return asyncio.Lock()

    async def _end_cmd(self):
        await asyncio.sleep(0.75)

    def _on_status_update(self, sender, data: WalkingPadCurStatus) -> None:
        """Update current state."""

        status: WalkingPadStatus = {
            "belt_state": (
                BeltState(data.belt_state)
                if data.belt_state in iter(BeltState)
                else BeltState.UNKNOWN
            ),
            "speed": data.speed / 10,
            "mode": WalkingPadMode(data.manual_mode),
            "session_distance": data.dist * 10,
            "session_running_time": data.time,
            "session_steps": data.steps,
            "status_timestamp": data.rtime,
        }

        if len(self._callbacks) > 0:
            for callback in self._callbacks:
                callback(status)

    def register_status_callback(self, callback) -> None:
        """Register a status callback."""
        self._callbacks.append(callback)

    @property
    def mac(self):
        """Mac address."""
        return self._ble_device.address

    @property
    def name(self):
        """Name."""
        return self._name

    @property
    def connection_status(self) -> WalkingPadConnectionStatus:
        """Connection status."""
        return self._connection_status

    @property
    def connected(self) -> bool:
        """Boolean property to check if the device is connected."""
        return self._connection_status == WalkingPadConnectionStatus.CONNECTED

    async def connect(self) -> None:
        """Connect the device."""
        lock = self._begin_cmd()
        if self._connection_status == WalkingPadConnectionStatus.CONNECTING:
            _LOGGER.info("Already connecting to WalkingPad")
            return
        _LOGGER.info("Connecting to WalkingPad")
        async with lock:
            self._connection_status = WalkingPadConnectionStatus.CONNECTING
            try:
                await self._controller.run(self._ble_device)
                self._connection_status = WalkingPadConnectionStatus.CONNECTED
            except (BleakError, TimeoutError) as err:
                _LOGGER.warning("Unable to connect to WalkingPad : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            except Exception:  # pylint: disable=broad-except
                _LOGGER.warning("Unable to connect to WalkingPad")
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            await self._end_cmd()

    async def disconnect(self) -> None:
        """Disconnect the device."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            return
        lock = self._begin_cmd()
        async with lock:
            try:
                await self._controller.disconnect()
            finally:
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
            await self._end_cmd()

    async def update_state(self) -> None:
        """Update device state."""
        # Grab the lock so we don't run while another command is running
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.ask_stats()
                # Skip callback so we don't reset debouncer
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def start_belt(self) -> None:
        """Start the belt."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.start_belt()
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def stop_belt(self) -> None:
        """Start the belt."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                await self._controller.stop_belt()
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED

    async def set_speed(self, speed: float) -> None:
        """Set the belt speed in km/h."""
        if self._connection_status == WalkingPadConnectionStatus.NOT_CONNECTED:
            await self.connect()
        lock = self._begin_cmd()
        async with lock:
            if not self.connected:
                return
            try:
                speed_tenths = int(speed * 10)
                await self._controller.change_speed(speed_tenths)
            except BleakError as err:
                _LOGGER.warning("Bluetooth error : %s", err)
                self._connection_status = WalkingPadConnectionStatus.NOT_CONNECTED
