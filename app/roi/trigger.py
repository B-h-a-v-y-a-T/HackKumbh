"""
Trigger Manager — Controls ROI processing state (NORMAL/ACTIVE).

Triggers increase the ROI detector's attention. They are NOT proof
of misconduct. They only activate higher-frequency checks.

States:
    NORMAL → lower-frequency ROI checks, low GPU usage
    ACTIVE → higher-frequency ROI checks, more attention

Transitions:
    trigger received → ACTIVE for configurable duration
    duration expires → COOLDOWN → NORMAL (unless new trigger)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

from app.schemas.common import ROIState, TriggerType

logger = logging.getLogger(__name__)


class TrackTriggerState:
    """State for a single tracked entity."""

    def __init__(
        self,
        active_duration: float = 5.0,
        cooldown_duration: float = 3.0,
    ) -> None:
        self.state: ROIState = ROIState.NORMAL
        self.last_trigger: Optional[TriggerType] = None
        self.last_trigger_time: float = 0.0
        self.active_until: float = 0.0
        self.cooldown_until: float = 0.0
        self.trigger_count: int = 0
        self._active_duration = active_duration
        self._cooldown_duration = cooldown_duration

    def activate(self, trigger: TriggerType) -> None:
        """Activate this track due to a trigger."""
        now = time.time()
        self.state = ROIState.ACTIVE
        self.last_trigger = trigger
        self.last_trigger_time = now
        self.active_until = now + self._active_duration
        self.trigger_count += 1
        logger.debug(
            f"Track activated: trigger={trigger.value}, "
            f"active_until={self.active_until:.1f}, "
            f"trigger_count={self.trigger_count}"
        )

    def update(self) -> ROIState:
        """Update state based on current time. Returns current state."""
        now = time.time()
        if self.state == ROIState.ACTIVE and now > self.active_until:
            # Active period expired
            self.cooldown_until = now + self._cooldown_duration
            self.state = ROIState.NORMAL
            logger.debug("Track returned to NORMAL after active period")
        return self.state

    @property
    def is_in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_trigger": self.last_trigger.value if self.last_trigger else None,
            "last_trigger_time": self.last_trigger_time,
            "trigger_count": self.trigger_count,
            "in_cooldown": self.is_in_cooldown,
        }


class TriggerManager:
    """
    Manages trigger states for all tracked entities.

    Thread-safe with async locks for concurrent API requests.
    """

    def __init__(
        self,
        active_duration: float = 5.0,
        cooldown_duration: float = 3.0,
    ) -> None:
        self._active_duration = active_duration
        self._cooldown_duration = cooldown_duration
        self._tracks: Dict[str, TrackTriggerState] = {}
        self._lock = asyncio.Lock()

    async def process_trigger(
        self, track_id: str, trigger: Optional[TriggerType]
    ) -> ROIState:
        """
        Process a trigger for a track.

        Args:
            track_id: Anonymous track identifier.
            trigger: The trigger type, or None for normal processing.

        Returns:
            Current ROI state after processing.
        """
        async with self._lock:
            if track_id not in self._tracks:
                self._tracks[track_id] = TrackTriggerState(
                    active_duration=self._active_duration,
                    cooldown_duration=self._cooldown_duration,
                )

            state = self._tracks[track_id]

            if trigger is not None:
                # Don't re-trigger during cooldown unless it's high-priority
                if state.is_in_cooldown and trigger not in (
                    TriggerType.OBJECT_ALREADY_DETECTED,
                    TriggerType.MANUAL_REVIEW_TRIGGER,
                ):
                    logger.debug(
                        f"Track {track_id}: trigger {trigger.value} ignored (cooldown)"
                    )
                else:
                    state.activate(trigger)

            return state.update()

    async def get_state(self, track_id: str) -> ROIState:
        """Get the current state for a track."""
        async with self._lock:
            if track_id not in self._tracks:
                return ROIState.NORMAL
            return self._tracks[track_id].update()

    async def get_all_states(self) -> Dict[str, dict]:
        """Get states for all tracks."""
        async with self._lock:
            return {
                tid: state.to_dict()
                for tid, state in self._tracks.items()
            }

    async def reset_track(self, track_id: str) -> None:
        """Reset a track to NORMAL state."""
        async with self._lock:
            if track_id in self._tracks:
                del self._tracks[track_id]

    def update_config(
        self,
        active_duration: Optional[float] = None,
        cooldown_duration: Optional[float] = None,
    ) -> None:
        """Update trigger configuration."""
        if active_duration is not None:
            self._active_duration = active_duration
        if cooldown_duration is not None:
            self._cooldown_duration = cooldown_duration
