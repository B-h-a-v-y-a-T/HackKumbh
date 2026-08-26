"""Pluggable Temporal Analysis Interface and Sequence Aggregator."""
import abc
import numpy as np
import torch
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.behaviour.schemas.pose import TrackPose
from app.behaviour.schemas.events import BehaviourEvent, ReasonCode
from .ctr_gcn import CTRGCNClassifier


class TemporalAnalysisResult(BaseModel):
    track_id: str
    dominant_class: str = "NORMAL_WRITING"
    probabilities: Dict[str, float] = Field(default_factory=dict)
    anomaly_probability: float = 0.0
    is_sustained: bool = False
    sustained_duration_sec: float = 0.0
    confidence: float = 1.0
    detected_events: List[BehaviourEvent] = Field(default_factory=list)
    reason_codes: List[ReasonCode] = Field(default_factory=list)


class TemporalAnalyzerInterface(abc.ABC):
    """Abstract interface for temporal skeleton sequence analyzers."""

    @abc.abstractmethod
    def predict_sequence(
        self,
        track_id: str,
        sequence_tensor: torch.Tensor,
        timestamp_ms: float
    ) -> TemporalAnalysisResult:
        """Analyzes a tensor of shape (1, C, T, V) and returns temporal behavior predictions."""
        pass


class TemporalSequenceBuffer:
    """Maintains sliding window of skeletal pose keypoints for temporal models."""

    def __init__(self, window_size: int = 30, num_joints: int = 17, in_channels: int = 3):
        self.window_size = window_size
        self.num_joints = num_joints
        self.in_channels = in_channels
        # {track_id: List of numpy arrays of shape (C, V)}
        self._buffers: Dict[str, List[np.ndarray]] = {}
        self._last_timestamps: Dict[str, float] = {}

    def add_frame(self, track: TrackPose, timestamp_ms: float) -> Optional[torch.Tensor]:
        """Appends a frame's keypoints to the track buffer.
        
        Returns:
            torch.Tensor of shape (1, C, T, V) when buffer has enough frames, else None.
        """
        track_id = track.track_id
        if track_id not in self._buffers:
            self._buffers[track_id] = []

        # Convert 17 keypoints into (C=3, V=17) array: (x, y, confidence)
        frame_mat = np.zeros((self.in_channels, self.num_joints), dtype=np.float32)
        for i, kp in enumerate(track.keypoints[:self.num_joints]):
            frame_mat[0, i] = kp.x
            frame_mat[1, i] = kp.y
            frame_mat[2, i] = kp.confidence if self.in_channels > 2 else 0.0

        buf = self._buffers[track_id]
        buf.append(frame_mat)
        self._last_timestamps[track_id] = timestamp_ms

        # Keep sliding window
        if len(buf) > self.window_size:
            buf.pop(0)

        if len(buf) >= 10:  # Can pad or run when at least 10 frames exist
            # Create array of shape (C, T, V)
            pad_needed = self.window_size - len(buf)
            if pad_needed > 0:
                padded = [buf[0]] * pad_needed + buf
            else:
                padded = buf

            # Stack into (T, C, V) -> permute to (C, T, V)
            seq_np = np.stack(padded, axis=1)  # (C, T, V)
            tensor = torch.from_numpy(seq_np).unsqueeze(0)  # (1, C, T, V)
            return tensor

        return None


class CTRGCNTemporalAnalyzer(TemporalAnalyzerInterface):
    """CTR-GCN powered Temporal Sequence Analyzer with leaky duration accumulator."""

    def __init__(
        self,
        model: Optional[CTRGCNClassifier] = None,
        sustained_thresh_sec: float = 2.0,
    ):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.model = model or CTRGCNClassifier()
        try:
            self.model.to(self.device)
        except Exception:
            self.device = "cpu"
        self.model.eval()
        self.sustained_thresh_sec = sustained_thresh_sec
        self.buffer = TemporalSequenceBuffer()

        # Duration state: {track_id: {"current_class": str, "duration_sec": float, "last_ms": float}}
        self._state: Dict[str, Dict] = {}
        self._last_infer_frame: Dict[str, int] = {}
        self._cached_results: Dict[str, TemporalAnalysisResult] = {}
        self._frame_count = 0

    def _get_state(self, track_id: str) -> Dict:
        if track_id not in self._state:
            self._state[track_id] = {
                "current_class": "NORMAL_WRITING",
                "duration_sec": 0.0,
                "last_ms": None,
            }
        return self._state[track_id]

    def predict_sequence(
        self,
        track_id: str,
        sequence_tensor: torch.Tensor,
        timestamp_ms: float
    ) -> TemporalAnalysisResult:
        """Executes forward pass through CTR-GCN on GPU."""
        with torch.no_grad():
            inp = sequence_tensor.to(self.device)
            logits = self.model(inp)
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        class_names = CTRGCNClassifier.CLASS_NAMES
        prob_dict = {name: float(probs[i]) for i, name in enumerate(class_names)}
        
        top_idx = int(np.argmax(probs))
        dominant_class = class_names[top_idx]
        anomaly_prob = float(1.0 - probs[0])  # Non-normal classes combined

        state = self._get_state(track_id)
        dt_sec = 0.0
        if state["last_ms"] is not None:
            dt_sec = max((timestamp_ms - state["last_ms"]) / 1000.0, 0.0)

        if dominant_class == state["current_class"]:
            state["duration_sec"] += dt_sec
        else:
            state["current_class"] = dominant_class
            state["duration_sec"] = 0.0

        state["last_ms"] = timestamp_ms

        is_sustained = (dominant_class != "NORMAL_WRITING") and (state["duration_sec"] >= self.sustained_thresh_sec)

        events: List[BehaviourEvent] = []
        reasons: List[ReasonCode] = []

        if is_sustained:
            events.append(BehaviourEvent.CTR_GCN_ANOMALOUS_POSE_PATTERN)
            if dominant_class == "NEIGHBOUR_PEEKING":
                events.append(BehaviourEvent.NEIGHBOUR_GAZE)
                reasons.append(ReasonCode.PROLONGED_NEIGHBOUR_GAZE_LEFT)
            elif dominant_class == "TORSO_ROTATION_ANOMALY":
                events.append(BehaviourEvent.TORSO_ROTATION)
                reasons.append(ReasonCode.TORSO_ROTATION_EXCEEDS_THRESHOLD)
            elif dominant_class == "DESK_BREACH_REACH":
                events.append(BehaviourEvent.HAND_OUTSIDE_DESK_ZONE)
                reasons.append(ReasonCode.WRIST_OUTSIDE_DESK_ZONE)

        res = TemporalAnalysisResult(
            track_id=track_id,
            dominant_class=dominant_class,
            probabilities=prob_dict,
            anomaly_probability=round(anomaly_prob, 3),
            is_sustained=is_sustained,
            sustained_duration_sec=round(state["duration_sec"], 2),
            confidence=round(float(probs[top_idx]), 3),
            detected_events=events,
            reason_codes=reasons,
        )
        self._cached_results[track_id] = res
        return res

    def _default_result(self, track_id: str) -> TemporalAnalysisResult:
        return TemporalAnalysisResult(
            track_id=track_id,
            dominant_class="NORMAL_WRITING",
            probabilities={"NORMAL_WRITING": 1.0},
            anomaly_probability=0.0,
            is_sustained=False,
            confidence=0.9,
        )

    def analyze_tracks_batch(
        self,
        tracks: List[TrackPose],
        timestamp_ms: float
    ) -> Dict[str, TemporalAnalysisResult]:
        """Runs batched forward pass for all active tracks in ONE GPU call."""
        self._frame_count += 1
        results: Dict[str, TemporalAnalysisResult] = {}
        tracks_to_infer: List[str] = []
        tensors_to_infer: List[torch.Tensor] = []

        for tr in tracks:
            seq_tensor = self.buffer.add_frame(tr, timestamp_ms)
            if seq_tensor is None:
                results[tr.track_id] = self._default_result(tr.track_id)
                continue

            last_f = self._last_infer_frame.get(tr.track_id, 0)
            if (self._frame_count - last_f >= 4) or (tr.track_id not in self._cached_results):
                tracks_to_infer.append(tr.track_id)
                tensors_to_infer.append(seq_tensor)
                self._last_infer_frame[tr.track_id] = self._frame_count
            else:
                results[tr.track_id] = self._cached_results[tr.track_id]

        if tensors_to_infer:
            batch_tensor = torch.cat(tensors_to_infer, dim=0).to(self.device)
            with torch.no_grad():
                logits = self.model(batch_tensor)
                probs_batch = torch.softmax(logits, dim=-1).cpu().numpy()

            class_names = CTRGCNClassifier.CLASS_NAMES
            for i, tid in enumerate(tracks_to_infer):
                probs = probs_batch[i]
                prob_dict = {name: float(probs[j]) for j, name in enumerate(class_names)}
                top_idx = int(np.argmax(probs))
                dominant_class = class_names[top_idx]
                anomaly_prob = float(1.0 - probs[0])

                state = self._get_state(tid)
                dt_sec = 0.0
                if state["last_ms"] is not None:
                    dt_sec = max((timestamp_ms - state["last_ms"]) / 1000.0, 0.0)

                if dominant_class == state["current_class"]:
                    state["duration_sec"] += dt_sec
                else:
                    state["current_class"] = dominant_class
                    state["duration_sec"] = 0.0

                state["last_ms"] = timestamp_ms

                is_sustained = (dominant_class != "NORMAL_WRITING") and (state["duration_sec"] >= self.sustained_thresh_sec)

                events: List[BehaviourEvent] = []
                reasons: List[ReasonCode] = []

                if is_sustained:
                    events.append(BehaviourEvent.CTR_GCN_ANOMALOUS_POSE_PATTERN)
                    if dominant_class == "NEIGHBOUR_PEEKING":
                        events.append(BehaviourEvent.NEIGHBOUR_GAZE)
                        reasons.append(ReasonCode.PROLONGED_NEIGHBOUR_GAZE_LEFT)
                    elif dominant_class == "TORSO_ROTATION_ANOMALY":
                        events.append(BehaviourEvent.TORSO_ROTATION)
                        reasons.append(ReasonCode.TORSO_ROTATION_EXCEEDS_THRESHOLD)
                    elif dominant_class == "DESK_BREACH_REACH":
                        events.append(BehaviourEvent.HAND_OUTSIDE_DESK_ZONE)
                        reasons.append(ReasonCode.WRIST_OUTSIDE_DESK_ZONE)

                res = TemporalAnalysisResult(
                    track_id=tid,
                    dominant_class=dominant_class,
                    probabilities=prob_dict,
                    anomaly_probability=round(anomaly_prob, 3),
                    is_sustained=is_sustained,
                    sustained_duration_sec=round(state["duration_sec"], 2),
                    confidence=round(float(probs[top_idx]), 3),
                    detected_events=events,
                    reason_codes=reasons,
                )
                self._cached_results[tid] = res
                results[tid] = res

        return results

    def analyze_track(self, track: TrackPose, timestamp_ms: float) -> TemporalAnalysisResult:
        """Convenience method accepting TrackPose, updating buffer, and running inference."""
        res_dict = self.analyze_tracks_batch([track], timestamp_ms)
        return res_dict.get(track.track_id, self._default_result(track.track_id))
