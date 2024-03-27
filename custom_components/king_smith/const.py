"""Constants for the walkingpad integration."""

from enum import Enum, unique
from typing import TypedDict

DOMAIN = "king_smith"


@unique
class BeltState(Enum):
    """An enumeration of the possible belt states."""

    STOPPED = 0
    ACTIVE = 1
    STANDBY = 5


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
