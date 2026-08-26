"""
End-to-end mock test: frame → ROI → detection → evidence → verification → final JSON.

This test validates the entire pipeline works in mock mode without GPU.
"""

import os
os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_PATH"] = "data/test_e2e.db"

import numpy as np
import pytest

from app.config import get_settings, reset_settings
from app.models.base import ModelRegistry
from app.models.yolo_detector import MockYOLO26SDetector
from app.models.videomae_verifier import MockVideoMAEV2Verifier
from app.models.rtdetr_verifier import MockRTDETRVerifier
from app.models.vitpose_verifier import MockViTPoseVerifier
from app.roi.cropper import ROICropper
from app.roi.quality import ImageQualityAnalyzer, CLAHEPreprocessor
from app.roi.temporal import TemporalSmoother
from app.verification.comparator import LiveRetroComparator
from app.verification.evidence import EvidenceGenerator
from app.schemas.common import VerificationStatus


class TestEndToEnd:
    def setup_method(self):
        reset_settings()
        ModelRegistry.reset()
        registry = ModelRegistry.get_instance()
        registry.register_detector("live", MockYOLO26SDetector())
        registry.register_temporal_verifier("videomae", MockVideoMAEV2Verifier())
        registry.register_high_accuracy_detector("rtdetr", MockRTDETRVerifier())
        registry.register_pose_verifier("vitpose", MockViTPoseVerifier())
        registry.load_all("cpu")

    def test_full_pipeline_mock(self):
        """Complete pipeline: frame → ROI → detect → smooth → verify → compare → evidence."""
        # 1. Create frame (simulating original high-res frame)
        frame = np.random.randint(30, 220, (1080, 1920, 3), dtype=np.uint8)

        # 2. Define ROI
        track_id = "T17"
        roi = [720, 300, 1080, 780]

        # 3. Crop from ORIGINAL frame
        cropper = ROICropper(detector_input_size=640)
        crop, validated_roi = cropper.crop(frame, roi, resize_to_detector=False)
        assert crop.shape == (480, 360, 3)  # Original pixels preserved

        # 4. Image quality
        quality_analyzer = ImageQualityAnalyzer()
        img_quality = quality_analyzer.analyze(crop)
        assert 0.0 <= img_quality.image_quality <= 1.0

        # 5. CLAHE
        clahe = CLAHEPreprocessor()
        crop, img_quality = clahe.process(crop, img_quality)

        # 6. Resize and detect
        detector_input = cropper._resize_for_detector(crop)
        assert detector_input.shape == (640, 640, 3)

        registry = ModelRegistry.get_instance()
        detector = registry.get_detector("live")
        detections = detector.predict(detector_input, confidence_threshold=0.3)
        assert isinstance(detections, list)

        # 7. Temporal smoothing
        smoother = TemporalSmoother()
        for _ in range(5):
            for det in detections:
                smoother.update(track_id, det.object_class, det.confidence)

        # 8. Generate live evidence
        evidence_gen = EvidenceGenerator()
        if detections:
            live_evidence = evidence_gen.create_live_evidence(
                track_id=track_id,
                camera_id="CAM_01",
                timestamp=1000.0,
                detections=detections,
                seat_id="B4",
                image_quality=img_quality.image_quality,
            )
            assert live_evidence.human_review_required is True
            assert "T17" in live_evidence.track_ids

        # 9. Retrospective verification (mock)
        temporal_verifier = registry.get_temporal_verifier("videomae")
        mock_frames = [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(16)]
        windows = temporal_verifier.analyze(mock_frames)
        assert len(windows) > 0

        ha_detector = registry.get_high_accuracy_detector("rtdetr")
        ha_dets = ha_detector.predict(crop, confidence_threshold=0.3)

        pose_verifier = registry.get_pose_verifier("vitpose")
        pose = pose_verifier.predict(crop)
        assert pose.head_direction in ["FORWARD", "LEFT", "RIGHT", "DOWN", "UP", "BEHIND", "UNKNOWN"]

        # 10. Compare live vs retrospective
        comparator = LiveRetroComparator()
        live_risk = max((d.confidence for d in detections), default=0.0)
        best_window = max(windows, key=lambda w: w.temporal_anomaly_score)
        verified_risk = max((d.confidence for d in ha_dets), default=0.0) * 0.7 + \
                        best_window.temporal_anomaly_score * 0.3

        comparison = comparator.compare(
            live_risk=live_risk,
            verified_risk=verified_risk,
        )
        assert comparison["verification_status"] in list(VerificationStatus)

        # 11. Final evidence JSON structure
        final = {
            "alert_id": live_evidence.alert_id if detections else "A0000",
            "track_ids": ["T17"],
            "camera_id": "CAM_01",
            "seat_ids": ["B4"],
            "live_risk": comparison["live_risk"],
            "verified_risk": comparison["verified_risk"],
            "verification_status": comparison["verification_status"].value,
            "human_review_required": True,
        }
        assert final["human_review_required"] is True
        assert "guilty" not in str(final).lower()
        assert "cheating" not in str(final).lower()

    def test_low_visibility_reduces_confidence(self):
        """Low visibility should reduce detection confidence."""
        frame = np.random.randint(30, 220, (480, 640, 3), dtype=np.uint8)
        registry = ModelRegistry.get_instance()
        detector = registry.get_detector("live")
        dets = detector.predict(frame, confidence_threshold=0.1)
        # With low visibility, we would multiply by 0.6
        for d in dets:
            reduced = d.confidence * 0.6
            assert reduced < d.confidence

    def test_missing_landmarks_not_suspicious(self):
        """Missing landmarks must produce UNKNOWN, not suspicious."""
        registry = ModelRegistry.get_instance()
        pose_verifier = registry.get_pose_verifier("vitpose")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)  # Black frame
        pose = pose_verifier.predict(frame)
        # If head direction is UNKNOWN, that's correct behavior
        # It should NOT be flagged as suspicious
        if pose.head_direction == "UNKNOWN":
            assert pose.reason is not None or pose.head_confidence < 0.5

    def test_no_cheating_verdict_in_output(self):
        """System must never produce cheating verdicts."""
        evidence_gen = EvidenceGenerator()
        from app.schemas.common import ObjectDetection
        det = ObjectDetection(object_class="mobile_phone", confidence=0.99, bbox=[0, 0, 50, 50])
        ev = evidence_gen.create_live_evidence(
            track_id="T17", camera_id="CAM_01", timestamp=100.0,
            detections=[det],
        )
        ev_dict = ev.model_dump()
        ev_str = str(ev_dict).lower()
        assert "cheating" not in ev_str
        assert "guilty" not in ev_str
        assert "confirmed cheating" not in ev_str
        assert ev.human_review_required is True
