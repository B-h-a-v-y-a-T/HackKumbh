"""
Test fixtures and shared configuration.
"""

import os
import sys

# Force mock mode for all tests
os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_PATH"] = "data/test_copycop.db"

import pytest
import numpy as np
from pathlib import Path


@pytest.fixture
def sample_frame():
    """Generate a sample BGR frame (1920x1080)."""
    rng = np.random.RandomState(42)
    return rng.randint(50, 200, (1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def small_frame():
    """Generate a small BGR frame (640x480)."""
    rng = np.random.RandomState(42)
    return rng.randint(50, 200, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_roi():
    """Standard student/desk ROI."""
    return [720, 300, 1080, 780]


@pytest.fixture
def sample_roi_request():
    """Sample ROI detection request as dict."""
    return {
        "camera_id": "CAM_01",
        "track_id": "T17",
        "seat_id": "B4",
        "roi": [720, 300, 1080, 780],
        "visibility": 0.91,
        "occlusion_score": 0.12,
        "trigger": "HAND_OUTSIDE_DESK",
        "timestamp": 1724074812.42,
    }


@pytest.fixture
def overexposed_frame():
    """Frame with severe overexposure."""
    frame = np.full((480, 640, 3), 252, dtype=np.uint8)
    frame[100:300, 100:400] = 255  # Clipped region
    return frame


@pytest.fixture
def dark_frame():
    """Very dark frame — most pixels near black to trigger underexposure."""
    rng = np.random.RandomState(42)
    return rng.randint(0, 4, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def low_contrast_frame():
    """Frame with very low contrast."""
    return np.full((480, 640, 3), 128, dtype=np.uint8) + \
           np.random.RandomState(42).randint(-3, 4, (480, 640, 3), dtype=np.int8).view(np.uint8)


@pytest.fixture
def settings():
    """Test settings."""
    from app.config import get_settings, reset_settings
    reset_settings()
    s = get_settings()
    return s


@pytest.fixture
def mock_registry():
    """Set up model registry with mock models."""
    from app.models.base import ModelRegistry
    from app.models.yolo_detector import MockYOLO26SDetector
    from app.models.videomae_verifier import MockVideoMAEV2Verifier
    from app.models.rtdetr_verifier import MockRTDETRVerifier
    from app.models.vitpose_verifier import MockViTPoseVerifier

    ModelRegistry.reset()
    registry = ModelRegistry.get_instance()
    registry.register_detector("live", MockYOLO26SDetector())
    registry.register_temporal_verifier("videomae", MockVideoMAEV2Verifier())
    registry.register_high_accuracy_detector("rtdetr", MockRTDETRVerifier())
    registry.register_pose_verifier("vitpose", MockViTPoseVerifier())
    registry.load_all("cpu")
    return registry
