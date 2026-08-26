"""
Automated Test Suite for Live Webcam Monitoring and Video Feeds in Timeline/Replay.
"""

import asyncio
import base64
import time
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_live_status_and_privacy_guarantees():
    """Verify live monitoring status endpoint returns privacy guarantees and telemetry."""
    with TestClient(app) as client:
        res = client.get("/api/v1/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ONLINE"
        assert "privacy_guarantees" in data
        assert data["privacy_guarantees"]["biometrics_stored"] is False
        assert data["privacy_guarantees"]["face_recognition_enabled"] is False
        assert data["privacy_guarantees"]["anonymous_tracking_only"] is True


def test_source_selection_flow():
    """Verify source switching between mock, video, and client live."""
    with TestClient(app) as client:
        # 1. Get initial source
        res = client.get("/api/v1/source")
        assert res.status_code == 200
        assert "available_modes" in res.json()

        # 2. Select video source
        res_vid = client.post("/api/v1/source/select", json={
            "mode": "video",
            "video_path": "demo_feed_1.mp4"
        })
        assert res_vid.status_code == 200
        assert res_vid.json()["mode"] == "video"
        assert res_vid.json()["video_path"] == "demo_feed_1.mp4"

        # 3. Select client live source
        res_client = client.post("/api/v1/source/select", json={
            "mode": "client_live"
        })
        assert res_client.status_code == 200
        assert res_client.json()["mode"] == "client_live"

        # 4. Select mock source
        res_mock = client.post("/api/v1/source/select", json={
            "mode": "mock"
        })
        assert res_mock.status_code == 200
        assert res_mock.json()["mode"] == "mock"

        # 5. Invalid mode rejected
        res_inv = client.post("/api/v1/source/select", json={
            "mode": "invalid_mode"
        })
        assert res_inv.status_code == 400


def test_video_feeds_list_and_upload():
    """Verify discovery of preloaded feeds and video upload functionality."""
    with TestClient(app) as client:
        # 1. List preloaded classroom feeds
        res_list = client.get("/api/v1/videos/list")
        assert res_list.status_code == 200
        videos = res_list.json().get("videos", [])
        assert len(videos) > 0
        filenames = [v["filename"] for v in videos]
        assert "demo_feed_1.mp4" in filenames

        # 2. Upload a test video file
        dummy_video_bytes = b"FAKE_MP4_HEADER_DATA_FOR_TESTING"
        files = {"file": ("test_upload_classroom.mp4", dummy_video_bytes, "video/mp4")}
        res_up = client.post("/api/v1/video/upload", files=files)
        assert res_up.status_code == 200
        up_data = res_up.json()
        assert up_data["status"] == "uploaded"
        assert up_data["filename"] == "test_upload_classroom.mp4"
        assert up_data["url"] == "/media/test_upload_classroom.mp4"


@pytest.mark.asyncio
async def test_mjpeg_stream_feed_response():
    """Verify that the MJPEG streaming endpoint streams multipart frames."""
    from app.api.live import stream_feed
    res = await stream_feed()
    assert res.status_code == 200
    assert "multipart/x-mixed-replace" in res.media_type

    gen = res.body_iterator
    first_chunk = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
    assert len(first_chunk) > 0
    assert b"--frame" in first_chunk


def test_timeline_replay_metadata_and_feeds():
    """Verify track timeline contains video feeds and replay synchronization metadata."""
    with TestClient(app) as client:
        # 1. Fetch timeline for track T17
        res = client.get("/api/v1/tracks/T17/timeline")
        assert res.status_code == 200
        data = res.json()
        assert data["track_id"] == "T17"
        assert "active_video_feed" in data
        assert "available_video_feeds" in data
        assert len(data["available_video_feeds"]) > 0
        assert "timeline" in data
        assert len(data["timeline"]) > 0

        # Check replay metadata on timeline entries
        for entry in data["timeline"]:
            assert "video_url" in entry
            assert "video_offset_sec" in entry

        # 2. List timeline feeds
        res_feeds = client.get("/api/v1/timeline/feeds")
        assert res_feeds.status_code == 200
        feeds = res_feeds.json().get("feeds", [])
        assert len(feeds) > 0
        assert any(f["filename"] == "demo_feed_1.mp4" for f in feeds)

        # 3. Start timeline replay
        res_replay = client.post("/api/v1/timeline/replay/start", json={
            "video_path": "demo_feed_1.mp4",
            "track_id": "T17",
            "start_time_sec": 10.0
        })
        assert res_replay.status_code == 200
        assert res_replay.json()["status"] == "REPLAY_STARTED"
        assert res_replay.json()["video_path"] == "demo_feed_1.mp4"


def test_websocket_client_webcam_processing():
    """Verify WebSocket client webcam processing (FRAME_IN -> FRAME_OUT)."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws:
            # 1. Receive initial greeting
            greeting = ws.receive_json()
            assert greeting["type"] == "SYSTEM_CONNECTED"

            # 2. Send ping, receive pong
            ws.send_text("ping")
            pong = ws.receive_json()
            assert pong["type"] == "pong"

            # 3. Create a synthetic test webcam frame (100x100 BGR)
            test_img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.rectangle(test_img, (20, 20), (80, 80), (255, 255, 255), -1)
            _, buf = cv2.imencode(".jpg", test_img)
            b64_str = base64.b64encode(buf.tobytes()).decode("utf-8")
            data_url = f"data:image/jpeg;base64,{b64_str}"

            # Send FRAME_IN
            ws.send_json({
                "type": "FRAME_IN",
                "image": data_url
            })

            # Receive FRAME_OUT
            response_packet = ws.receive_json()
            assert response_packet["type"] in ("FRAME_OUT", "FRAME_TELEMETRY")
            if response_packet["type"] == "FRAME_OUT":
                assert "image" in response_packet
                assert response_packet["image"].startswith("data:image/jpeg;base64,")
                assert "tracks" in response_packet
