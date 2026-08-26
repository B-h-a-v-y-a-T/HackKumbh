"""Tests for evidence and privacy."""

import pytest
from app.privacy.sanitizer import PrivacySanitizer, validate_no_pii, sanitize_evidence


class TestPrivacySanitizer:
    def test_clean_data_passes(self):
        data = {"track_id": "T17", "camera_id": "CAM_01", "seat_id": "B4"}
        warnings = validate_no_pii(data)
        assert len(warnings) == 0

    def test_email_detected(self):
        data = {"track_id": "T17", "email": "student@example.com"}
        warnings = validate_no_pii(data)
        assert len(warnings) > 0

    def test_name_field_detected(self):
        data = {"student_name": "John Doe", "track_id": "T17"}
        warnings = validate_no_pii(data)
        assert len(warnings) > 0

    def test_roll_number_detected(self):
        data = {"roll_number": "2024CS101", "track_id": "T17"}
        warnings = validate_no_pii(data)
        assert len(warnings) > 0

    def test_sanitize_strips_pii(self):
        data = {
            "track_id": "T17",
            "student_name": "John",
            "camera_id": "CAM_01",
            "face_embedding": [0.1, 0.2],
        }
        clean = sanitize_evidence(data)
        assert "student_name" not in clean
        assert "face_embedding" not in clean
        assert "track_id" in clean
        assert "camera_id" in clean

    def test_sanitizer_tracks_violations(self):
        s = PrivacySanitizer()
        s.check_and_sanitize({"name": "test", "track_id": "T1"})
        assert s.violation_count > 0


class TestEvidenceStore:
    def test_clip_id_generation(self):
        from app.storage.evidence_store import EvidenceStore
        store = EvidenceStore(retention_enabled=True)
        cid1 = store.generate_clip_id("A001", 100.0)
        cid2 = store.generate_clip_id("A002", 100.0)
        assert cid1.startswith("EC_")
        assert cid1 != cid2

    def test_retention_disabled_no_save(self):
        from app.storage.evidence_store import EvidenceStore
        store = EvidenceStore(retention_enabled=False)
        result = store.save_clip("test_clip", b"fake_video_data")
        assert result is None

    def test_retention_enabled_saves(self, tmp_path):
        from app.storage.evidence_store import EvidenceStore
        store = EvidenceStore(storage_path=str(tmp_path), retention_enabled=True)
        result = store.save_clip("EC_test123", b"fake_video_data")
        assert result is not None
        assert result["clip_id"] == "EC_test123"
        assert (tmp_path / "EC_test123.mp4").exists()
