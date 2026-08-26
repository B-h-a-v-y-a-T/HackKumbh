# CopyCop — Privacy-First AI Video Analytics for Examination Monitoring

A standalone, production-ready AI examination monitoring system. Produces **structured evidence** for human review — **never automatic cheating verdicts**.

## Integrated 4-Part Architecture

Drishti unifies live perception, behaviour & spatial intelligence, high-resolution ROI verification, and real-time dashboard orchestration:

1. **Part 1 — Live Perception, Pose & Tracking** (`app/perception/`):
   - Fast YOLO-pose body detection (17 keypoints) + ByteTrack multi-person tracking
   - Autonomous seat auto-discovery and spatial desk association
   - Robust head yaw/pitch orientation, body geometry, and occlusion/visibility estimation
2. **Part 2 — Behaviour & Spatial Intelligence** (`app/behaviour/`):
   - Continuous individual risk tracking with leaky accumulator and exponential decay
   - Personal baseline adaptation (fidget vs. deliberate turning)
   - Spatial group intelligence: coordinated gaze chains, passing pairs, and communication graphs
   - Temporal sequence evaluation (CTR-GCN spatial graph convolutions)
   - False-positive control with invigilator proximity suppression
3. **Part 3 — High-Resolution ROI Detection & Retrospective Verification** (`app/roi/`, `app/verification/`):
   - Attention-triggered high-resolution student/desk ROI extraction from original frames
   - Image quality assessment (overexposure, underexposure, blur) + adaptive CLAHE
   - Phone, paper chit, and prohibited object detection (YOLO26-S)
   - Temporal object evidence smoothing
   - Retrospective video verification via VideoMAE V2-L temporal scanning + RT-DETRv4-L + ViTPose++-L
4. **Part 4 — Dashboard, Orchestration & Invigilator Review** (`app/api/`, `app/static/`):
   - High-throughput asynchronous pipeline worker (25+ FPS)
   - Real-time WebSocket telemetry (`/ws/live`) and MJPEG video feed (`/api/v1/stream/feed`)
   - Modern dark-themed dashboard console (`/`) with live video stream, student risk console, and alert drawer
   - Human-in-the-loop invigilator decision recording and audit logging
   - Strict privacy safeguards (zero biometrics, zero face recognition, identity-free anonymous tracking)

---

## End-to-End Data Flow

```
CAMERA / VIDEO / MOCK
         ↓
[Part 1: Live Perception] ──→ YOLO-pose (17 keypoints) + ByteTrack Tracking
         ↓
    StudentState (Canonical anonymous state: track_id, seat_id, keypoints, head yaw, desk ROI)
         ↓
[Part 2: Behaviour Intelligence] ──→ Head Gaze + Torso + Hand Zones + Baselines + Group Chains
         ↓
    Behaviour Events & Continuous Risk Score
         ↓
[ROI Trigger Bridge] ──→ If risk exceeds threshold or suspicious sequence detected
         ↓
[Part 3: High-Res ROI & Object Detection] ──→ High-Res Crop + CLAHE + YOLO26-S Object Detection
         ↓
[Retrospective Video Verification] ──→ VideoMAE V2-L Temporal Scan + RT-DETRv4-L + ViTPose++-L
         ↓
[Unified Risk Engine] ──→ Composite explainable risk score from all sources
         ↓
[Part 4: Real-Time Dashboard & Invigilator Console] ──→ WebSocket + Live Stream + Human Review
```

---

## Quick Start

### 1. Install

```bash
cd Drishti
pip install -r requirements.txt
cp .env.example .env   # Or use existing .env
```

### 2. Run the Server (Mock Mode by Default)

```bash
python -m uvicorn app.main:app --reload
```

The system is now live:
- **Real-Time Interactive Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Evidence Verification Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **WebSocket Stream**: `ws://localhost:8000/ws/live`
- **MJPEG Live Feed**: [http://localhost:8000/api/v1/stream/feed](http://localhost:8000/api/v1/stream/feed)

The API is now running at `http://localhost:8000`. Try:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/models
```

### 3. Generate Mock Data

```bash
python scripts/generate_mock_data.py
```

Creates `data/mock/exam_frame.jpg` and `data/mock/sample_video.mp4`.

### 4. Run the Demo

```bash
python demo.py
```

Demonstrates the full pipeline: frame → ROI → detection → evidence → verification → comparison.

### 5. Run Tests

```bash
MOCK_MODE=true pytest tests/ -v
```

## API Documentation

Interactive docs available at `http://localhost:8000/docs` when running.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health, model status, uptime |
| GET | `/models` | Loaded models and status |
| POST | `/models/reload` | Hot-reload models |
| GET | `/config` | Current configuration |
| PUT | `/config` | Update runtime configuration |
| POST | `/roi/detect` | Single-frame ROI detection |
| POST | `/roi/detect/upload` | ROI detection with frame upload |
| POST | `/roi/batch` | Batch ROI detection |
| POST | `/verification/run` | Queue retrospective verification job |
| GET | `/verification/{job_id}` | Check job status/progress |
| GET | `/evidence/{alert_id}` | Retrieve structured evidence |
| GET | `/metrics` | Performance and resource metrics |

### Live ROI Detection

```bash
curl -X POST http://localhost:8000/roi/detect \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "CAM_01",
    "track_id": "T17",
    "seat_id": "B4",
    "frame_path": "data/mock/exam_frame.jpg",
    "roi": [720, 300, 1080, 780],
    "visibility": 0.91,
    "trigger": "HAND_OUTSIDE_DESK",
    "timestamp": 1724074812.42
  }'
```

### Retrospective Verification

```bash
# Submit job
curl -X POST http://localhost:8000/verification/run \
  -H "Content-Type: application/json" \
  -d '{
    "video_path": "data/mock/sample_video.mp4",
    "start_time": 0,
    "end_time": 30
  }'

# Check status
curl http://localhost:8000/verification/{job_id}
```

## Input Modes

| Mode | Endpoint | Input | Output |
|------|----------|-------|--------|
| A — Single-frame | POST /roi/detect | Frame + ROI | Object detections |
| B — Live ROI | POST /roi/detect (repeated) | Frames + ROI + trigger | Temporally-smoothed evidence |
| C — Retrospective | POST /verification/run | Video + time range | Suspicious windows + verification |

## JSON Schemas

### ROI Detection Request
```json
{
  "camera_id": "CAM_01",
  "track_id": "T17",
  "seat_id": "B4",
  "frame_path": "data/mock/exam_frame.jpg",
  "roi": [720, 300, 1080, 780],
  "visibility": 0.91,
  "occlusion_score": 0.12,
  "trigger": "HAND_OUTSIDE_DESK",
  "timestamp": 1724074812.42
}
```

### Evidence Event
```json
{
  "alert_id": "A0001",
  "track_ids": ["T17"],
  "camera_id": "CAM_01",
  "seat_ids": ["B4"],
  "start_time": 642.2,
  "end_time": 651.8,
  "events": ["OBJECT_INTERACTION"],
  "objects": [{"object_class": "mobile_phone", "confidence": 0.94, "bbox": [82, 121, 164, 207]}],
  "verification_confidence": 0.91,
  "status": "STRENGTHENED",
  "human_review_required": true
}
```

## Training YOLO26-S

### Dataset Setup

```
datasets/contraband/
  images/{train,val,test}/
  labels/{train,val,test}/
  data.yaml
```

See [datasets/contraband/README.md](datasets/contraband/README.md) for annotation format and class definitions.

### Train

```bash
python scripts/train_yolo.py --data datasets/contraband/data.yaml --epochs 100 --device 0
```

### Evaluate

```bash
python scripts/evaluate.py --model runs/train/contraband/weights/best.pt
```

### Export to ONNX/TensorRT

```bash
python scripts/export_model.py --model runs/train/contraband/weights/best.pt --format onnx
python scripts/export_model.py --model runs/train/contraband/weights/best.pt --format engine
```

## Configuration

All settings via `.env` or environment variables. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_MODE` | `true` | No GPU, fake detections |
| `MODEL_DEVICE` | `cpu` | `cuda`, `cpu`, `mps` |
| `DEFAULT_OBJECT_CONFIDENCE` | `0.5` | Base confidence threshold |
| `PHONE_CONFIDENCE_THRESHOLD` | `0.45` | Phone-specific threshold |
| `ROI_ACTIVE_DURATION_SECONDS` | `5` | Trigger active period |
| `ROI_COOLDOWN_SECONDS` | `3` | Trigger cooldown |
| `VERIFICATION_INTERVAL_MINUTES` | `15` | Retrospective interval |
| `RAW_VIDEO_RETENTION_ENABLED` | `false` | Keep raw footage |
| `EVIDENCE_RETENTION_ENABLED` | `true` | Keep evidence clips |
| `EVIDENCE_RETENTION_HOURS` | `24` | Evidence expiry |

See [.env.example](.env.example) for all options.

## Privacy Design

**Core principle**: The system produces evidence, never identifies individuals.

- ✅ Anonymous track IDs (T17, T18, T19)
- ✅ Camera IDs, seat IDs, timestamps
- ✅ Object detections, pose evidence, confidence scores
- ✅ Configurable retention with automatic cleanup
- ❌ No face recognition or embeddings
- ❌ No student names or roll numbers
- ❌ No biometric matching
- ❌ No audio recording/analysis
- ❌ No identity recognition of any kind

Raw video is **not permanently retained by default**. Evidence clips are auto-deleted after the configurable retention period.

## Performance

- Live ROI detection: optimized for low latency (crop from original, single model inference)
- Retrospective verification: allowed to be slower (multi-model, async background)
- Models loaded once and cached in registry
- GPU batching support
- ROI caching, configurable frame sampling
- TensorRT/ONNX export for deployment optimization

Monitor via `GET /metrics`:
```json
{
  "requests_total": 142,
  "avg_latency_ms": 23.5,
  "active_verification_jobs": 1,
  "cpu_percent": 12.3,
  "memory_rss_mb": 450.2,
  "gpu": {"device": "NVIDIA RTX 4090", "memory_allocated_mb": 2048.0}
}
```

## Project Structure

```
app/
    main.py                  # FastAPI application
    config.py                # Pydantic settings
    api/                     # API endpoints
    models/                  # Model abstractions (YOLO, VideoMAE, RT-DETR, ViTPose)
    roi/                     # ROI pipeline (cropper, quality, trigger, temporal)
    verification/            # Retrospective pipeline
    schemas/                 # Pydantic request/response models
    workers/                 # Background job workers
    privacy/                 # Retention, sanitization
    storage/                 # Database, evidence store
scripts/                     # Training, evaluation, export, mock data
datasets/                    # Dataset configs
tests/                       # Unit, integration, e2e tests
demo.py                      # Standalone demo
```

## Known Limitations

1. **No pre-trained exam-specific weights**: YOLO26-S ships with COCO weights. Fine-tuning requires a custom exam dataset.
2. **VideoMAE V2-L anomaly scoring**: The temporal anomaly score is derived from feature magnitudes. Fine-tuning on exam-specific behaviours would improve accuracy.
3. **RT-DETRv4-L availability**: Uses RT-DETR-L weights via Ultralytics. The v4 architecture can be dropped in when weights are publicly available.
4. **ViTPose++ Large**: Uses the base ViTPose model via HuggingFace. Larger variants require the full MMPose setup.
5. **Evidence clips**: Require FFmpeg installed for subclip extraction.
6. **RTSP support**: Architecture is RTSP-compatible but current implementation is file-based.
7. **Model accuracy claims**: No accuracy claims are made without evaluation on a real exam dataset. Always evaluate on your data before deployment.

## License

Internal use. Not for distribution.
