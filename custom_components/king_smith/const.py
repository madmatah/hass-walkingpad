"""Constants for the walkingpad integration."""

from enum import Enum, unique
from typing import Final, TypedDict

# Re-export BeltState and ProtocolType from the library so that all
# integration modules can continue importing them from .const.
from walkingpad_controller import BeltState, ProtocolType

DOMAIN = "king_smith"


CONF_REMOTE_CONTROL: Final = "remote_control"
CONF_REMOTE_CONTROL_ENABLED: Final = "remote_control_enabled"
CONF_MAC: Final = "mac"
CONF_MODE: Final = "mode"
CONF_NAME: Final = "name"
CONF_PREFERRED_MODE: Final = "preferred_mode"


@unique
class WalkingPadMode(Enum):
    """An enumeration of the possible WalkingPad modes."""

    AUTO = 0
    MANUAL = 1
    STANDBY = 2


DEFAULT_PREFERRED_MODE: Final = WalkingPadMode.MANUAL.name.lower()
PREFERRED_MODE_OPTIONS: Final = [
    WalkingPadMode.AUTO.name.lower(),
    WalkingPadMode.MANUAL.name.lower(),
]


class WalkingPadStatus(TypedDict):
    """A type to represent the state of the WalkingPad at a specific time."""

    belt_state: BeltState
    speed: float  # speed in km/h
    mode: WalkingPadMode
    session_running_time: int  # in seconds
    session_distance: int  # distance in meters
    session_steps: int
    session_calories: int  # total energy in kcal (FTMS only)
    status_timestamp: float
