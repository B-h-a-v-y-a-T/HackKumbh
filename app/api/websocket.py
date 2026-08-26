"""
Unified WebSocket — Single event stream for all real-time data.

Supports:
  - StudentState updates
  - Behaviour events + group events
  - Object detections
  - Risk updates
  - Retrospective verification updates
  - Dashboard notifications
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections for real-time telemetry broadcast."""

    def __init__(self):
        self.active: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.active.append(ws)
        logger.info("WebSocket client connected (total: %d)", len(self.active))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)
        logger.info("WebSocket client disconnected (total: %d)", len(self.active))

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to all connected clients."""
        async with self._lock:
            stale = []
            for ws in self.active:
                try:
                    await ws.send_json(data)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self.active.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self.active)


# Global connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """
    Real-time telemetry broadcast and bidirectional client webcam processing.

    The WebSocket streams unified telemetry including:
    - StudentState from perception pipeline
    - Behaviour events and risk scores from behaviour engine
    - Group events from spatial intelligence
    - Object detections from ROI detector
    - Retrospective verification updates
    """
    await ws_manager.connect(ws)

    from app.pipeline.worker import get_worker
    import base64
    import cv2
    import numpy as np

    stop_event = asyncio.Event()

    async def receive_loop():
        try:
            while not stop_event.is_set():
                msg_text = await ws.receive_text()
                client_msg = json.loads(msg_text)

                if client_msg.get("type") == "PING":
                    await ws.send_json({"type": "PONG", "timestamp": client_msg.get("timestamp", 0)})
                elif client_msg.get("type") == "FRAME_IN":
                    # Client uploaded webcam frame
                    image_data = client_msg.get("image", "")
                    if image_data.startswith("data:image"):
                        header, b64_data = image_data.split(",", 1)
                        img_bytes = base64.b64decode(b64_data)
                        nparr = np.frombuffer(img_bytes, np.uint8)
                        frame_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        worker = get_worker()
                        if worker and frame_bgr is not None:
                            worker._frame_id += 1
                            pipeline = worker._get_pipeline()
                            p1_output = None
                            if pipeline is not None:
                                try:
                                    p1_output = pipeline.process_frame(frame_bgr)
                                except Exception as ex:
                                    logger.debug("Perception error on client frame: %s", ex)

                            if p1_output is not None:
                                from app.behaviour.adapter import pipeline_output_to_frame_input
                                frame_input = pipeline_output_to_frame_input(p1_output, worker._frame_id)
                                analysis = worker.risk_engine.process_frame(frame_input)
                                risk_by_track = {t.track_id: t for t in analysis.tracks}
                                annotated = worker._visualizer.draw(frame_bgr, p1_output, risk_by_track=risk_by_track)
                            else:
                                mock_frame = worker.mock_generator.generate_frame()
                                analysis = worker.risk_engine.process_frame(mock_frame)
                                frame_input = mock_frame
                                annotated = frame_bgr

                            if annotated is not None:
                                _, enc_buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
                                out_b64 = base64.b64encode(enc_buf).decode("utf-8")
                                out_image = f"data:image/jpeg;base64,{out_b64}"
                            else:
                                out_image = image_data

                            packet = worker._build_packet(frame_input, analysis, scenario="WEBCAM")
                            packet["type"] = "FRAME_OUT"
                            packet["image"] = out_image
                            await ws.send_json(packet)
        except WebSocketDisconnect:
            stop_event.set()
        except Exception as e:
            logger.debug("WebSocket receive loop ended: %s", e)
            stop_event.set()

    async def send_loop():
        last_broadcast_frame = -1
        try:
            while not stop_event.is_set():
                worker = get_worker()
                if worker:
                    _, packet, _ = worker.get_latest_frame()
                    if packet and packet.get("frame_id") != last_broadcast_frame:
                        last_broadcast_frame = packet.get("frame_id")
                        await ws.send_json(packet)
                await asyncio.sleep(0.01)  # 100 Hz polling for instant delivery
        except WebSocketDisconnect:
            stop_event.set()
        except Exception as e:
            logger.debug("WebSocket send loop ended: %s", e)
            stop_event.set()

    recv_task = asyncio.create_task(receive_loop())
    send_task = asyncio.create_task(send_loop())

    try:
        await stop_event.wait()
    finally:
        recv_task.cancel()
        send_task.cancel()
        await ws_manager.disconnect(ws)


async def broadcast_frame_telemetry(packet: Dict[str, Any]) -> None:
    """Broadcast a telemetry packet to all connected WebSocket clients."""
    await ws_manager.broadcast(packet)


async def broadcast_behaviour_event(event: Dict[str, Any]) -> None:
    """Broadcast a behaviour event to all connected clients."""
    event["type"] = "BEHAVIOUR_EVENT"
    await ws_manager.broadcast(event)


async def broadcast_risk_update(risk_data: Dict[str, Any]) -> None:
    """Broadcast a risk update to all connected clients."""
    risk_data["type"] = "RISK_UPDATE"
    await ws_manager.broadcast(risk_data)


async def broadcast_verification_update(verification: Dict[str, Any]) -> None:
    """Broadcast a retrospective verification update."""
    verification["type"] = "VERIFICATION_UPDATE"
    await ws_manager.broadcast(verification)
