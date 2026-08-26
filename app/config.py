"""
CopyCop - Centralized Configuration

All settings loaded from environment variables / .env file.
No values are hard-coded; everything is configurable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    app_name: str = "CopyCop"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # --- Mock Mode ---
    mock_mode: bool = True

    # --- Model Configuration ---
    model_device: str = "cuda"
    live_model: str = "yolo26s"
    yolo_custom_weights: Optional[str] = None
    rtdetr_weights: str = "rtdetr-l.pt"
    videomae_model: str = "OpenGVLab/VideoMAEv2-Large"
    vitpose_model: str = "nielsr/vitpose-base"

    # --- Roboflow Phone Detector ---
    roboflow_model_id: str = "phone-detection-3d9gh/1"
    roboflow_api_key: Optional[str] = None
    roboflow_phone_confidence: float = 0.45
    roboflow_iou_threshold: float = 0.45
    phone_confirmation_frames: int = 3

    # --- Live ROI Detection ---
    default_object_confidence: float = 0.5
    phone_confidence_threshold: float = 0.45
    chit_confidence_threshold: float = 0.40
    prohibited_confidence_threshold: float = 0.50
    detector_input_size: int = 640

    # --- Trigger System ---
    roi_active_duration_seconds: float = 5.0
    roi_cooldown_seconds: float = 3.0

    # --- Temporal Smoothing ---
    temporal_window_phone: int = 5
    temporal_window_chit: int = 5
    temporal_window_behaviour: int = 10
    temporal_threshold_phone: float = 0.6
    temporal_threshold_chit: float = 0.5
    temporal_threshold_behaviour: float = 0.7

    # --- Retrospective Verification ---
    verification_interval_minutes: int = 15
    temporal_scan_window_seconds: float = 10.0
    temporal_scan_stride_seconds: float = 5.0
    temporal_top_k_windows: int = 5
    temporal_anomaly_threshold: float = 0.6
    verification_frame_sample_fps: float = 2.0

    # --- Evidence ---
    evidence_clip_pre_seconds: float = 3.0
    evidence_clip_post_seconds: float = 3.0

    # --- Privacy / Retention ---
    raw_video_retention_enabled: bool = False
    evidence_retention_enabled: bool = True
    evidence_retention_hours: int = 24

    # --- Storage ---
    database_path: str = "data/copycop.db"
    evidence_storage_path: str = "data/evidence"

    # --- Part 1: Perception Pipeline ---
    perception_enabled: bool = True
    perception_model: str = "yolo11n-pose.pt"
    perception_confidence: float = 0.30
    perception_device: str = "cuda"
    perception_imgsz: int = 640
    camera_source: str = "0"
    camera_id: str = "CAM_01"
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30

    # --- Head Pose Estimation (SixDRepNet) ---
    head_pose_enabled: bool = True
    head_pose_model: str = "sixdrepnet_repvgg_a0"
    head_pose_checkpoint: str = "data/models/sixdrepnet_repvgg_a0.pth"
    head_pose_device: str = "auto"
    head_pose_interval: int = 3
    head_pose_alpha: float = 0.35
    head_pose_min_crop_width: int = 32
    head_pose_min_crop_height: int = 32
    head_pose_min_confidence: float = 0.35
    head_pose_use_fp16: bool = True
    debug_behaviour_overlay: bool = True

    # --- Part 2: Behaviour Intelligence ---
    behaviour_enabled: bool = True
    behaviour_attack_rate: float = 0.85
    behaviour_decay_rate: float = 0.35
    risk_trigger_threshold: int = 40  # Risk score above which Part 3 ROI is triggered
    ctr_gcn_enabled: bool = False
    ctr_gcn_use_for_risk: bool = False

    # --- Part 4: Server & Live Streaming ---
    source_mode: str = "mock"  # "mock", "video", "live"
    websocket_telemetry_fps: float = 25.0
    mjpeg_stream_fps: float = 30.0

    # --- Performance ---
    max_concurrent_verification_jobs: int = 2
    gpu_batch_size: int = 4

    def get_confidence_threshold(self, object_class: str) -> float:
        """Get the class-specific confidence threshold."""
        thresholds = {
            "mobile_phone": self.phone_confidence_threshold,
            "paper_chit": self.chit_confidence_threshold,
            "prohibited_object": self.prohibited_confidence_threshold,
        }
        return thresholds.get(object_class, self.default_object_confidence)

    def get_temporal_window(self, object_class: str) -> int:
        """Get the class-specific temporal smoothing window size."""
        windows = {
            "mobile_phone": self.temporal_window_phone,
            "paper_chit": self.temporal_window_chit,
        }
        return windows.get(object_class, self.temporal_window_behaviour)

    def get_temporal_threshold(self, object_class: str) -> float:
        """Get the class-specific temporal evidence threshold."""
        thresholds = {
            "mobile_phone": self.temporal_threshold_phone,
            "paper_chit": self.temporal_threshold_chit,
        }
        return thresholds.get(object_class, self.temporal_threshold_behaviour)

    @property
    def database_dir(self) -> Path:
        p = Path(self.database_path).parent
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def evidence_dir(self) -> Path:
        p = Path(self.evidence_storage_path)
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
