"""Personal Behaviour Baseline Calibration Engine."""
import numpy as np
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import ReasonCode


class StudentBaselineProfile(BaseModel):
    track_id: str
    sample_count: int = 0
    mean_yaw: float = 0.0
    std_yaw: float = 8.0          # default natural variation in degrees
    mean_pitch: float = -20.0     # normal writing angle
    std_pitch: float = 10.0
    mean_torso_rot: float = 0.0
    std_torso_rot: float = 5.0
    mean_kinetic_energy: float = 0.01
    std_kinetic_energy: float = 0.005
    is_naturally_fidgety: bool = False
    is_calibrated: bool = False


class BaselineDeviationResult(BaseModel):
    track_id: str
    deviation_score: float = 0.0      # Standardized Z-score deviation
    yaw_deviation: float = 0.0
    torso_deviation: float = 0.0
    energy_deviation: float = 0.0
    is_meaningful_deviation: bool = False
    is_natural_fidget: bool = False
    profile_summary: Dict = Field(default_factory=dict)


class PersonalBaselineManager:
    """Maintains short-term rolling baseline per anonymous track_id.
    
    Prevents false alarms for naturally restless/fidgety students by calibrating
    to individual movement distributions and updating baselines dynamically.
    """

    def __init__(
        self,
        calibration_window_size: int = 90,   # ~3-5 seconds of frames at 20-30 fps
        z_score_significance_threshold: float = 2.5,
        ema_alpha: float = 0.03,             # Slow adaptive baseline update
    ):
        self.window_size = calibration_window_size
        self.z_thresh = z_score_significance_threshold
        self.ema_alpha = ema_alpha

        # Per-track sample buffers: {track_id: {"yaw": [], "pitch": [], "torso": [], "energy": []}}
        self._buffers: Dict[str, Dict[str, List[float]]] = {}
        self._profiles: Dict[str, StudentBaselineProfile] = {}

    def _get_buffer(self, track_id: str) -> Dict[str, List[float]]:
        if track_id not in self._buffers:
            self._buffers[track_id] = {
                "yaw": [],
                "pitch": [],
                "torso": [],
                "energy": [],
            }
        return self._buffers[track_id]

    def get_profile(self, track_id: str) -> StudentBaselineProfile:
        if track_id not in self._profiles:
            self._profiles[track_id] = StudentBaselineProfile(track_id=track_id)
        return self._profiles[track_id]

    def set_custom_baseline(
        self,
        track_id: str,
        mean_yaw: float = 0.0,
        std_yaw: float = 18.0,
        mean_kinetic_energy: float = 0.05,
        std_kinetic_energy: float = 0.02,
        is_fidgety: bool = True
    ):
        """Allows initializing or pinning a calibrated baseline (e.g. for neurodiverse/fidgety profile)."""
        profile = self.get_profile(track_id)
        profile.mean_yaw = mean_yaw
        profile.std_yaw = max(std_yaw, 4.0)
        profile.mean_kinetic_energy = mean_kinetic_energy
        profile.std_kinetic_energy = max(std_kinetic_energy, 0.002)
        profile.is_naturally_fidgety = is_fidgety
        profile.is_calibrated = True
        self._profiles[track_id] = profile

    def update_and_evaluate(
        self,
        track_id: str,
        current_yaw: float,
        current_pitch: float,
        current_torso_rot: float,
        current_kinetic_energy: float,
        is_currently_suspicious: bool = False
    ) -> BaselineDeviationResult:
        """Updates rolling baseline and evaluates how much current behaviour deviates."""
        buf = self._get_buffer(track_id)
        profile = self.get_profile(track_id)

        # 1. Evaluate current deviation against profile BEFORE polluting baseline
        eps = 1e-4
        z_yaw = abs(current_yaw - profile.mean_yaw) / (profile.std_yaw + eps)
        z_torso = abs(current_torso_rot - profile.mean_torso_rot) / (profile.std_torso_rot + eps)
        z_energy = max(0.0, current_kinetic_energy - profile.mean_kinetic_energy) / (profile.std_kinetic_energy + eps)

        # Maximum standardized deviation
        max_dev = float(max(z_yaw, z_torso, z_energy * 0.7))

        is_meaningful = max_dev >= self.z_thresh
        is_natural_fidget = False

        if profile.is_naturally_fidgety and max_dev < (self.z_thresh * 1.6):
            # Suppress false positives for known fidgety students
            is_meaningful = False
            is_natural_fidget = True

        # 2. Update buffer and baseline ONLY if current behavior is not in severe anomaly
        # to prevent baseline poisoning
        if not is_currently_suspicious:
            buf["yaw"].append(current_yaw)
            buf["pitch"].append(current_pitch)
            buf["torso"].append(current_torso_rot)
            buf["energy"].append(current_kinetic_energy)

            if len(buf["yaw"]) > self.window_size:
                buf["yaw"].pop(0)
                buf["pitch"].pop(0)
                buf["torso"].pop(0)
                buf["energy"].pop(0)

            profile.sample_count = len(buf["yaw"])

            if len(buf["yaw"]) >= 15 and (len(buf["yaw"]) % 5 == 0 or not profile.is_calibrated):
                # Recalculate rolling statistics periodically
                profile.mean_yaw = float(np.mean(buf["yaw"]))
                profile.std_yaw = float(max(np.std(buf["yaw"]), 5.0))  # Minimum 5 deg natural slack
                profile.mean_pitch = float(np.mean(buf["pitch"]))
                profile.std_pitch = float(max(np.std(buf["pitch"]), 6.0))
                profile.mean_torso_rot = float(np.mean(buf["torso"]))
                profile.std_torso_rot = float(max(np.std(buf["torso"]), 4.0))
                profile.mean_kinetic_energy = float(np.mean(buf["energy"]))
                profile.std_kinetic_energy = float(max(np.std(buf["energy"]), 0.002))
                
                # Check if naturally fidgety
                if profile.std_kinetic_energy > 0.015 or profile.std_yaw > 14.0:
                    profile.is_naturally_fidgety = True
                
                profile.is_calibrated = True

        return BaselineDeviationResult(
            track_id=track_id,
            deviation_score=round(max_dev, 2),
            yaw_deviation=round(z_yaw, 2),
            torso_deviation=round(z_torso, 2),
            energy_deviation=round(z_energy, 2),
            is_meaningful_deviation=is_meaningful,
            is_natural_fidget=is_natural_fidget,
            profile_summary={
                "mean_yaw": round(profile.mean_yaw, 1),
                "std_yaw": round(profile.std_yaw, 1),
                "mean_energy": round(profile.mean_kinetic_energy, 4),
                "is_fidgety": profile.is_naturally_fidgety,
                "calibrated": profile.is_calibrated,
            }
        )
