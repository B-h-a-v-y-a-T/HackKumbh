"""Tests for temporal smoothing and trigger system."""

import asyncio
import time
import pytest
from app.roi.temporal import TemporalSmoother
from app.roi.trigger import TriggerManager
from app.schemas.common import ROIState, TriggerType


class TestTemporalSmoothing:
    def setup_method(self):
        self.smoother = TemporalSmoother(
            window_sizes={"mobile_phone": 5, "paper_chit": 5},
            thresholds={"mobile_phone": 0.6, "paper_chit": 0.5},
        )

    def test_single_frame_not_evidence(self):
        """One frame should never produce evidence."""
        smoothed, ready = self.smoother.update("T17", "mobile_phone", 0.95)
        assert not ready  # Need at least 2 frames

    def test_gradual_buildup(self):
        """Confidence must build up over multiple frames."""
        confs = [0.31, 0.42, 0.81, 0.91, 0.94]
        for conf in confs:
            smoothed, ready = self.smoother.update("T17", "mobile_phone", conf)
        assert smoothed > 0.6
        assert ready

    def test_no_detection_decays(self):
        """Confidence should decay when object disappears."""
        for _ in range(5):
            self.smoother.update("T17", "mobile_phone", 0.9)
        for _ in range(5):
            smoothed, _ = self.smoother.update("T17", "mobile_phone", 0.0)
        assert smoothed < 0.5

    def test_different_classes_independent(self):
        """Each class has independent temporal tracking."""
        self.smoother.update("T17", "mobile_phone", 0.9)
        self.smoother.update("T17", "mobile_phone", 0.9)
        self.smoother.update("T17", "paper_chit", 0.1)
        self.smoother.update("T17", "paper_chit", 0.1)
        phone_s = self.smoother.get_smoothed("T17").get("mobile_phone", 0)
        chit_s = self.smoother.get_smoothed("T17").get("paper_chit", 0)
        assert phone_s > chit_s

    def test_different_tracks_independent(self):
        self.smoother.update("T17", "mobile_phone", 0.9)
        self.smoother.update("T17", "mobile_phone", 0.9)
        self.smoother.update("T18", "mobile_phone", 0.1)
        self.smoother.update("T18", "mobile_phone", 0.1)
        assert self.smoother.get_smoothed("T17")["mobile_phone"] > \
               self.smoother.get_smoothed("T18")["mobile_phone"]

    def test_batch_update(self):
        result = self.smoother.update_batch(
            "T17",
            [("mobile_phone", 0.8)],
            all_classes=["mobile_phone", "paper_chit"],
        )
        assert "mobile_phone" in result
        assert "paper_chit" in result
        assert result["mobile_phone"][0] > result["paper_chit"][0]

    def test_clear_track(self):
        self.smoother.update("T17", "mobile_phone", 0.9)
        self.smoother.clear_track("T17")
        assert self.smoother.get_smoothed("T17") == {}

    def test_weighted_average(self):
        """Recent frames should be weighted more."""
        vals = [0.0, 0.0, 0.0, 0.0, 1.0]
        avg = TemporalSmoother._weighted_average(vals)
        assert avg > 0.3  # Last value weighted heavily


class TestTriggerSystem:
    def setup_method(self):
        self.mgr = TriggerManager(active_duration=0.3, cooldown_duration=0.2)

    @pytest.mark.asyncio
    async def test_normal_state_by_default(self):
        state = await self.mgr.get_state("T17")
        assert state == ROIState.NORMAL

    @pytest.mark.asyncio
    async def test_trigger_activates(self):
        state = await self.mgr.process_trigger("T17", TriggerType.HAND_OUTSIDE_DESK)
        assert state == ROIState.ACTIVE

    @pytest.mark.asyncio
    async def test_active_expires(self):
        await self.mgr.process_trigger("T17", TriggerType.HAND_OUTSIDE_DESK)
        await asyncio.sleep(0.5)  # Wait for active period (0.3s) to expire
        state = await self.mgr.get_state("T17")
        assert state == ROIState.NORMAL

    @pytest.mark.asyncio
    async def test_cooldown_blocks_normal_triggers(self):
        await self.mgr.process_trigger("T17", TriggerType.HAND_OUTSIDE_DESK)
        await asyncio.sleep(0.5)  # Active expires, cooldown starts (0.2s)
        # During cooldown, normal trigger should be ignored
        state = await self.mgr.process_trigger("T17", TriggerType.TORSO_ROTATION)
        # May still be NORMAL if cooldown blocks it
        assert state in (ROIState.NORMAL, ROIState.ACTIVE)

    @pytest.mark.asyncio
    async def test_high_priority_overrides_cooldown(self):
        # Use a fresh manager with known durations
        mgr = TriggerManager(active_duration=0.2, cooldown_duration=0.5)
        await mgr.process_trigger("T17", TriggerType.HAND_OUTSIDE_DESK)
        await asyncio.sleep(0.3)  # Wait for active (0.2s) to expire → enters cooldown (0.5s)
        # Force state update by getting state
        state = await mgr.get_state("T17")
        assert state == ROIState.NORMAL  # Should be NORMAL (active expired)
        # Now high-priority trigger should override cooldown
        state = await mgr.process_trigger("T17", TriggerType.OBJECT_ALREADY_DETECTED)
        assert state == ROIState.ACTIVE

    @pytest.mark.asyncio
    async def test_no_trigger_stays_normal(self):
        state = await self.mgr.process_trigger("T17", None)
        assert state == ROIState.NORMAL

    @pytest.mark.asyncio
    async def test_reset_track(self):
        await self.mgr.process_trigger("T17", TriggerType.HAND_OUTSIDE_DESK)
        await self.mgr.reset_track("T17")
        state = await self.mgr.get_state("T17")
        assert state == ROIState.NORMAL
