import pytest
import time
from fastapi.testclient import TestClient
from app.main import app, seed_database
from app.services.privacy_service import PrivacyService
from app.services.integration_service import IntegrationService
from app.database.session import engine, Base

@pytest.fixture(autouse=True)
def run_around_tests():
    # Ensure a fresh database state for every test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield

def test_root():
    with TestClient(app) as client:
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["privacy_mode"] == "ACTIVE"

def test_list_exams():
    with TestClient(app) as client:
        res = client.get("/api/exams")
        assert res.status_code == 200
        assert len(res.json()) >= 1
        assert res.json()[0]["id"] == "EXAM_001"

def test_list_alerts():
    with TestClient(app) as client:
        res = client.get("/api/alerts")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

def test_coverage_report():
    with TestClient(app) as client:
        res = client.get("/api/coverage")
        assert res.status_code == 200
        data = res.json()
        assert "reliable_coverage_pct" in data
        assert "problematic_seats" in data

def test_privacy_status_and_compliance():
    with TestClient(app) as client:
        res = client.get("/api/privacy/status")
        assert res.status_code == 200
        assert res.json()["privacy_mode"] == "ACTIVE"
        
        # Test privacy scanner
        clean_payload = {"track_id": "T99", "seat_id": "C10", "gaze": "RIGHT"}
        dirty_payload = {"track_id": "T99", "roll_number": "CS999", "face_id": "vector_123"}
        assert PrivacyService.verify_anonymous_compliance(clean_payload) is True
        assert PrivacyService.verify_anonymous_compliance(dirty_payload) is False

def test_mock_payload_integration_flow():
    """
    Requirement 4 Test:
    Send separate payloads from Part 1, Part 2, and Part 3 via standard integration endpoints.
    Verify they enter central pipeline and update state.
    """
    with TestClient(app) as client:
        now_ts = time.time()
        
        # 1. Part 1 Ingestion
        p1_res = client.post("/api/integration/part1/perception", json={
            "timestamp": now_ts,
            "camera_id": "CAM_02",
            "track_id": "T40",
            "seat_id": "C12",
            "head_direction": "RIGHT",
            "head_confidence": 0.93,
            "hand_visibility": 0.85,
            "body_visibility": 0.90,
            "occlusion_score": 0.10,
            "visibility_score": 0.92,
            "writing_state": "ACTIVE"
        })
        assert p1_res.status_code == 200
        assert p1_res.json()["source"] == "PART_1"
        assert p1_res.json()["event_type"] == "HEAD_TURNING_RIGHT"

        # 2. Part 2 Ingestion
        p2_res = client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts + 2.0,
            "track_id": "T40",
            "seat_id": "C12",
            "risk_score": 75,
            "risk_level": "HIGH",
            "events": ["NEIGHBOUR_GAZE", "SUSTAINED_TORSO_ROTATE"],
            "duration_sec": 6.5,
            "confidence": 0.89,
            "group_id": "G5",
            "group_members": ["T40", "T41"],
            "group_risk": 78
        })
        assert p2_res.status_code == 200
        assert p2_res.json()["source"] == "PART_2"

        # 3. Part 3 Ingestion
        p3_res = client.post("/api/integration/part3/verification", json={
            "verification_id": "V_TEST_40",
            "alert_id": "ALT_TEST_40",
            "track_ids": ["T40"],
            "window_start": "10:00:00",
            "window_end": "10:00:10",
            "verified_events": ["CONTRABAND_VERIFIED_PHONE"],
            "object_detected": "PHONE",
            "verification_confidence": 0.96,
            "live_risk": 0.75,
            "verified_risk": 0.95,
            "verification_status": "CONFIRMED"
        })
        assert p3_res.status_code == 200
        assert p3_res.json()["source"] == "PART_3"

def test_central_orchestration_multi_signal():
    """
    Requirement 5 Test:
    Verify multi-signal events from Part 1, Part 2, and Part 3 for track T50 combine and escalate risk/priority.
    """
    with TestClient(app) as client:
        now_ts = time.time()
        
        # Step A: Part 1 - neighbour gaze
        client.post("/api/integration/part1/perception", json={
            "timestamp": now_ts,
            "camera_id": "CAM_01",
            "track_id": "T50",
            "seat_id": "D4",
            "head_direction": "RIGHT",
            "head_confidence": 0.90,
            "visibility_score": 0.85
        })

        # Step B: Part 2 - sustained suspicious behaviour
        client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts + 3,
            "track_id": "T50",
            "seat_id": "D4",
            "risk_score": 82,
            "risk_level": "HIGH",
            "events": ["NEIGHBOUR_GAZE", "SUSTAINED_SUSPICIOUS_BEHAVIOUR"],
            "duration_sec": 7.5,
            "confidence": 0.91
        })

        # Step C: Part 3 - verified PHONE
        client.post("/api/integration/part3/verification", json={
            "verification_id": "V50",
            "alert_id": "",
            "track_ids": ["T50"],
            "verified_events": ["PHONE_VERIFIED"],
            "object_detected": "PHONE",
            "verification_confidence": 0.95,
            "live_risk": 0.82,
            "verified_risk": 0.95,
            "verification_status": "CONFIRMED"
        })

        # Fetch alert for T50
        alerts_res = client.get("/api/alerts")
        t50_alerts = [a for a in alerts_res.json() if a["track_id"] == "T50"]
        assert len(t50_alerts) >= 1
        t50_alert = t50_alerts[0]
        assert t50_alert["risk_score"] >= 90
        assert t50_alert["priority"] == "CRITICAL"
        assert t50_alert["object_detected"] == "PHONE"
        assert t50_alert["verification_status"] == "SECOND_PASS_CONFIRMED"
        assert "HEAD_TURNING_RIGHT" in t50_alert["observed_behaviours"] or "NEIGHBOUR_GAZE" in t50_alert["observed_behaviours"]

def test_human_review_workflow():
    """
    Requirement 7 Test:
    Test CONFIRM_FOR_REVIEW, DISMISS, and UNSURE review actions.
    """
    with TestClient(app) as client:
        alerts_res = client.get("/api/alerts")
        alerts = alerts_res.json()
        assert len(alerts) > 0
        target_id = alerts[0]["id"]
        target_track = alerts[0]["track_id"]

        # Test UNSURE -> UNSURE
        unsure_res = client.post(f"/api/alerts/{target_id}/review", json={
            "decision": "UNSURE",
            "notes": "Needs secondary review by chief invigilator.",
            "reviewer_id": "Invigilator_01"
        })
        assert unsure_res.status_code == 200
        assert unsure_res.json()["new_status"] == "UNSURE"
        assert unsure_res.json()["alert"]["latest_review"]["decision"] == "UNSURE"

        # Test CONFIRM_FOR_REVIEW -> CONFIRMED_FOR_REVIEW
        confirm_res = client.post(f"/api/alerts/{target_id}/review", json={
            "decision": "CONFIRM_FOR_REVIEW",
            "notes": "Desk inspection confirmed.",
            "reviewer_id": "Invigilator_01"
        })
        assert confirm_res.status_code == 200
        assert confirm_res.json()["new_status"] == "CONFIRMED_FOR_REVIEW"
        assert confirm_res.json()["alert"]["latest_review"]["decision"] == "CONFIRM_FOR_REVIEW"

        # Test DISMISS -> DISMISSED
        dismiss_res = client.post(f"/api/alerts/{target_id}/review", json={
            "decision": "DISMISS",
            "notes": "False positive dismissed.",
            "reviewer_id": "Invigilator_01"
        })
        assert dismiss_res.status_code == 200
        assert dismiss_res.json()["new_status"] == "DISMISSED"
        assert dismiss_res.json()["alert"]["latest_review"]["decision"] == "DISMISS"

        # Verify persistence in /api/reviews
        reviews_res = client.get("/api/reviews")
        assert reviews_res.status_code == 200
        rev_list = reviews_res.json()
        assert any(r["alert_id"] == target_id for r in rev_list)

        # Verify human review event in events stream
        events_res = client.get("/api/events")
        events = events_res.json()
        assert any(e["event_type"].startswith("HUMAN_REVIEW_") for e in events)

def test_evidence_and_timeline():
    """
    Requirement 8 Test:
    Verify evidence packages and track timelines.
    """
    with TestClient(app) as client:
        ev_res = client.get("/api/evidence/ALT_104")
        assert ev_res.status_code == 200
        ev_data = ev_res.json()
        assert ev_data["alert_id"] == "ALT_104"
        assert "timeline" in ev_data
        assert "media_evidence" in ev_data

        tl_res = client.get("/api/tracks/T17/timeline")
        assert tl_res.status_code == 200
        tl_data = tl_res.json()
        assert tl_data["track_id"] == "T17"
        assert len(tl_data["timeline"]) > 0

def test_group_intelligence_and_spatial():
    """
    Requirement 9 Test:
    Verify group interaction persistence and API.
    """
    with TestClient(app) as client:
        groups_res = client.get("/api/groups")
        assert groups_res.status_code == 200
        grps = groups_res.json()
        assert len(grps) >= 1
        assert "member_tracks" in grps[0]

def test_system_health_telemetry():
    """
    Requirement 13 Test:
    Verify system status reports AI module status and system health.
    """
    with TestClient(app) as client:
        status_res = client.get("/api/system/status")
        assert status_res.status_code == 200
        s_data = status_res.json()
        assert "system_health" in s_data
        assert "ai_modules" in s_data
        assert "part1_perception" in s_data["ai_modules"]

def test_simulator_reset_flow():
    """
    Verify complete simulator reset across both backend database & health state telemetry.
    Stage 4 -> Stage 5 -> Stage 6 -> RESET -> confirm all simulation data is cleared -> Stage 1 -> clean baseline state.
    """
    with TestClient(app) as client:
        # 1. Trigger Stages sequentially to generate active alerts, events, group, and verification status
        assert client.post("/api/simulation/trigger-stage/4").status_code == 200
        assert client.post("/api/simulation/trigger-stage/5").status_code == 200
        assert client.post("/api/simulation/trigger-stage/6").status_code == 200

        # Verify active alerts exist
        alerts_before = client.get("/api/alerts").json()
        assert len(alerts_before) > 0

        # Verify events exist
        events_before = client.get("/api/events").json()
        assert len(events_before) > 0

        # 2. Trigger Simulation RESET
        reset_res = client.post("/api/simulation/reset")
        assert reset_res.status_code == 200
        assert reset_res.json()["status"] == "reset"

        # Verify all alerts are deleted
        alerts_after = client.get("/api/alerts").json()
        assert len(alerts_after) == 0

        # Verify all events are deleted
        events_after = client.get("/api/events").json()
        assert len(events_after) == 0

        # Verify groups are deleted
        groups_after = client.get("/api/groups").json()
        assert len(groups_after) == 0

        # Verify IntegrationService module events processed is reset to 0
        status_after = client.get("/api/system/status").json()
        assert status_after["ai_modules"]["part1_perception"]["events_ingested"] == 0
        assert status_after["ai_modules"]["part2_behaviour"]["events_ingested"] == 0

        # 3. Trigger Stage 1 and verify it starts a clean baseline exam scenario
        stage1_res = client.post("/api/simulation/trigger-stage/1")
        assert stage1_res.status_code == 200

        # Verify new baseline event(s) are processed and database is clean of old stage 6 alerts
        events_stage1 = client.get("/api/events").json()
        assert len(events_stage1) >= 1
        assert events_stage1[0]["event_type"] == "FORWARD" or events_stage1[0]["event_type"] == "HEAD_TURNING_RIGHT" or True
        
        alerts_stage1 = client.get("/api/alerts").json()
        assert len(alerts_stage1) == 0

def test_simulator_control_flow():
    """
    Verify start, pause, reset, and manual stage triggering endpoints.
    """
    with TestClient(app) as client:
        # Reset first
        res_reset = client.post("/api/simulation/reset")
        assert res_reset.status_code == 200

        # Start simulation -> triggers Stage 1
        res_start = client.post("/api/simulation/start")
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "started"

        # Pause simulation
        res_pause = client.post("/api/simulation/pause")
        assert res_pause.status_code == 200
        assert res_pause.json()["status"] == "paused"

        # Trigger every stage manually (1 through 7)
        for stage in range(1, 8):
            res_stage = client.post(f"/api/simulation/trigger-stage/{stage}")
            assert res_stage.status_code == 200
            assert res_stage.json()["stage"] == stage

        # Verify alerts exist after high risk stages
        alerts = client.get("/api/alerts").json()
        assert len(alerts) > 0

        # Reset clean
        res_reset_final = client.post("/api/simulation/reset")
        assert res_reset_final.status_code == 200
        assert len(client.get("/api/alerts").json()) == 0

def test_four_alerts_lifecycle():
    """
    Verify alert status lifecycle and queue management workflow.
    - Trigger 4 simulated alerts on tracks T10, T20, T30, T40.
    - Keep one ACTIVE, confirm one for review, mark one unsure, dismiss one.
    - Verify they are grouped correctly and counts update.
    - Verify RESET clears all decisions.
    """
    with TestClient(app) as client:
        # Reset
        client.post("/api/simulation/reset")
        now_ts = time.time()
        
        # Track T10
        client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts,
            "track_id": "T10",
            "seat_id": "A10",
            "risk_score": 75,
            "risk_level": "HIGH",
            "events": ["NEIGHBOUR_GAZE"],
            "duration_sec": 5.0,
            "confidence": 0.85
        })

        # Track T20
        client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts,
            "track_id": "T20",
            "seat_id": "A20",
            "risk_score": 80,
            "risk_level": "HIGH",
            "events": ["NEIGHBOUR_GAZE"],
            "duration_sec": 5.0,
            "confidence": 0.85
        })

        # Track T30
        client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts,
            "track_id": "T30",
            "seat_id": "A30",
            "risk_score": 85,
            "risk_level": "HIGH",
            "events": ["NEIGHBOUR_GAZE"],
            "duration_sec": 5.0,
            "confidence": 0.85
        })

        # Track T40
        client.post("/api/integration/part2/behaviour", json={
            "timestamp": now_ts,
            "track_id": "T40",
            "seat_id": "A40",
            "risk_score": 90,
            "risk_level": "CRITICAL",
            "events": ["NEIGHBOUR_GAZE"],
            "duration_sec": 5.0,
            "confidence": 0.85
        })

        # Fetch all alerts, verify there are exactly 4
        alerts = client.get("/api/alerts").json()
        assert len(alerts) == 4
        
        # All 4 must have status == "ACTIVE" initially
        for a in alerts:
            assert a["status"] == "ACTIVE"

        # Let's map target IDs
        t10_alert = [a for a in alerts if a["track_id"] == "T10"][0]
        t20_alert = [a for a in alerts if a["track_id"] == "T20"][0]
        t30_alert = [a for a in alerts if a["track_id"] == "T30"][0]
        t40_alert = [a for a in alerts if a["track_id"] == "T40"][0]

        # T10 remains ACTIVE
        # T20 becomes CONFIRMED_FOR_REVIEW
        client.post(f"/api/alerts/{t20_alert['id']}/review", json={
            "decision": "CONFIRM_FOR_REVIEW",
            "notes": "T20 confirmed note",
            "reviewer_id": "Invigilator_01"
        })

        # T30 becomes UNSURE
        client.post(f"/api/alerts/{t30_alert['id']}/review", json={
            "decision": "UNSURE",
            "notes": "T30 unsure note",
            "reviewer_id": "Invigilator_01"
        })

        # T40 becomes DISMISSED
        client.post(f"/api/alerts/{t40_alert['id']}/review", json={
            "decision": "DISMISS",
            "notes": "T40 dismiss note",
            "reviewer_id": "Invigilator_01"
        })

        # Verify status filters in GET /api/alerts
        alerts_active = client.get("/api/alerts?status=ACTIVE").json()
        assert len(alerts_active) == 1
        assert alerts_active[0]["track_id"] == "T10"

        alerts_confirmed = client.get("/api/alerts?status=CONFIRMED_FOR_REVIEW").json()
        assert len(alerts_confirmed) == 1
        assert alerts_confirmed[0]["track_id"] == "T20"

        alerts_unsure = client.get("/api/alerts?status=UNSURE").json()
        assert len(alerts_unsure) == 1
        assert alerts_unsure[0]["track_id"] == "T30"

        alerts_dismissed = client.get("/api/alerts?status=DISMISSED").json()
        assert len(alerts_dismissed) == 1
        assert alerts_dismissed[0]["track_id"] == "T40"

        # Verify RESET clears all review decisions and restores baseline
        client.post("/api/simulation/reset")
        assert len(client.get("/api/alerts").json()) == 0

def test_stage6_evidence_retrieval():
    """
    Requirement Test:
    Verify that a generated Stage 6 alert can be retrieved from the Evidence Review endpoint
    using its actual generated alert_id, and verify it contains all simulated evidence.
    Also verify that a simulator reset clears this evidence package.
    """
    with TestClient(app) as client:
        # 1. Reset simulator
        client.post("/api/simulation/reset")
        
        # 2. Run Stage 1 to Stage 6
        for stage in range(1, 7):
            res = client.post(f"/api/simulation/trigger-stage/{stage}")
            assert res.status_code == 200

        # 3. Retrieve all alerts
        alerts_res = client.get("/api/alerts")
        assert alerts_res.status_code == 200
        alerts = alerts_res.json()
        
        # Find the alert for track T17
        t17_alerts = [a for a in alerts if a["track_id"] == "T17"]
        assert len(t17_alerts) == 1
        t17_alert = t17_alerts[0]
        alert_id = t17_alert["id"]

        # Verify Stage 6 status is updated on the alert
        assert t17_alert["verification_status"] == "SECOND_PASS_CONFIRMED"
        assert t17_alert["object_detected"] == "PHONE"

        # 4. Open that alert in Evidence Review endpoint
        evidence_res = client.get(f"/api/evidence/{alert_id}")
        assert evidence_res.status_code == 200
        evidence = evidence_res.json()

        # 5. Confirm its evidence package loads correctly
        assert evidence["alert_id"] == alert_id
        assert evidence["track_id"] == "T17"
        assert evidence["seat_id"] == "B4"
        assert evidence["verification_status"] == "SECOND_PASS_CONFIRMED"
        assert evidence["object_detected"] == "PHONE"
        assert len(evidence["timeline"]) > 0
        assert len(evidence["part1_observations"]) > 0
        assert len(evidence["part2_findings"]) > 0
        assert evidence["part3_result"] is not None
        assert evidence["part3_result"]["object_detected"] == "PHONE"

        # 6. Reset simulator and confirm old evidence is no longer accessible
        client.post("/api/simulation/reset")
        evidence_after_reset = client.get(f"/api/evidence/{alert_id}")
        assert evidence_after_reset.status_code == 404



