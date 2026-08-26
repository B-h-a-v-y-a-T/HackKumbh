"""Tests for verification jobs and live/retro comparison."""

import pytest
from app.verification.comparator import LiveRetroComparator
from app.schemas.common import VerificationStatus, ObjectDetection


class TestComparator:
    def setup_method(self):
        self.comp = LiveRetroComparator()

    def test_no_change(self):
        r = self.comp.compare(live_risk=0.3, verified_risk=0.35)
        assert r["verification_status"] == VerificationStatus.NO_CHANGE

    def test_strengthened(self):
        r = self.comp.compare(live_risk=0.3, verified_risk=0.8)
        assert r["verification_status"] == VerificationStatus.STRENGTHENED

    def test_weakened(self):
        r = self.comp.compare(live_risk=0.8, verified_risk=0.5)
        assert r["verification_status"] == VerificationStatus.WEAKENED

    def test_new_event(self):
        r = self.comp.compare(live_risk=0.05, verified_risk=0.85)
        assert r["verification_status"] == VerificationStatus.NEW_EVENT

    def test_confirmed_evidence(self):
        r = self.comp.compare(live_risk=0.7, verified_risk=0.75)
        assert r["verification_status"] == VerificationStatus.CONFIRMED_EVIDENCE

    def test_insufficient_visibility(self):
        r = self.comp.compare(live_risk=0.5, verified_risk=0.5, visibility_ok=False)
        assert r["verification_status"] == VerificationStatus.INSUFFICIENT_VISIBILITY

    def test_new_event_from_detections(self):
        dets = [ObjectDetection(object_class="mobile_phone", confidence=0.9, bbox=[0, 0, 50, 50])]
        r = self.comp.compare(
            live_risk=0.05, verified_risk=0.4,
            verified_detections=dets, live_detections=None,
        )
        assert r["verification_status"] == VerificationStatus.NEW_EVENT

    def test_time_window_format(self):
        s = self.comp.format_time_window(3742.0, 3751.0)
        assert "01:02:22" in s


class TestEvidenceGeneration:
    def test_live_evidence_has_review_flag(self):
        from app.verification.evidence import EvidenceGenerator
        gen = EvidenceGenerator()
        det = ObjectDetection(object_class="mobile_phone", confidence=0.9, bbox=[0, 0, 50, 50])
        ev = gen.create_live_evidence(
            track_id="T17", camera_id="CAM_01", timestamp=100.0,
            detections=[det], seat_id="B4",
        )
        assert ev.human_review_required is True
        assert ev.source == "live"
        assert "T17" in ev.track_ids

    def test_retrospective_evidence_has_review_flag(self):
        from app.verification.evidence import EvidenceGenerator
        gen = EvidenceGenerator()
        ev = gen.create_retrospective_evidence(
            track_ids=["T17"], camera_id="CAM_01",
            start_time=642.0, end_time=651.0,
            detections=[], status=VerificationStatus.NEW_EVENT,
        )
        assert ev.human_review_required is True
        assert ev.source == "retrospective"

    def test_clip_time_range(self):
        from app.verification.evidence import EvidenceGenerator
        gen = EvidenceGenerator(clip_pre_seconds=3.0, clip_post_seconds=3.0)
        start, end = gen.get_clip_time_range(10.0, 20.0)
        assert start == 7.0
        assert end == 23.0
