"""Constants for the walkingpad integration."""

from enum import Enum, IntEnum, unique
from typing import Final, TypedDict

DOMAIN = "king_smith"


CONF_REMOTE_CONTROL: Final = "remote_control"
CONF_REMOTE_CONTROL_ENABLED: Final = "remote_control_enabled"
CONF_MAC: Final = "mac"
CONF_MODE: Final = "mode"
CONF_NAME: Final = "name"


@unique
class BeltState(IntEnum):
    """An enumeration of the possible belt states."""

    STOPPED = 0
    ACTIVE = 1
    STANDBY = 5
    STARTING = 9
    UNKNOWN = 1000


@unique
class WalkingPadMode(Enum):
    """An enumeration of the possible WalkingPad modes."""

    AUTO = 0
    MANUAL = 1
    STANDBY = 2


class WalkingPadStatus(TypedDict):
    """A type to represent the state of the WalkingPad at a specific time."""

    belt_state: BeltState
    speed: float  # speed in km/h
    mode: WalkingPadMode
    session_running_time: int  # in seconds
    session_distance: int  # distance in meters
    session_steps: int
    status_timestamp: float
