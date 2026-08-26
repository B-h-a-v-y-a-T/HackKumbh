"""
CopyCop Demo — Demonstrates the complete pipeline.

Usage:
    python demo.py

Demonstrates:
    1. Load sample examination frame
    2. Create student ROI
    3. Run YOLO detection (mock or real)
    4. Show detected objects
    5. Generate structured evidence
    6. Run simulated retrospective verification
    7. Compare live and retrospective results
    8. Print final evidence JSON

Output always ends with: "Human review required."
Never: "Cheating confirmed."
"""

import json
import os
import sys
import time

# Ensure mock mode for demo
os.environ.setdefault("MOCK_MODE", "true")

import numpy as np


def main():
    print("=" * 60)
    print("  COPYCOP -- AI Video Analytics Demo")
    print("  Privacy-First Examination Monitoring")
    print("=" * 60)
    print()

    # --- Setup ---
    from app.config import get_settings
    settings = get_settings()
    print(f"Mode: {'MOCK' if settings.mock_mode else 'LIVE'}")
    print(f"Device: {settings.model_device}")
    print()

    # Register and load models
    from app.models.base import ModelRegistry
    from app.models.yolo_detector import MockYOLO26SDetector
    from app.models.videomae_verifier import MockVideoMAEV2Verifier
    from app.models.rtdetr_verifier import MockRTDETRVerifier
    from app.models.vitpose_verifier import MockViTPoseVerifier

    registry = ModelRegistry.get_instance()
    registry.register_detector("live", MockYOLO26SDetector())
    registry.register_temporal_verifier("videomae", MockVideoMAEV2Verifier())
    registry.register_high_accuracy_detector("rtdetr", MockRTDETRVerifier())
    registry.register_pose_verifier("vitpose", MockViTPoseVerifier())
    registry.load_all("cpu")
    print("Models loaded (mock mode)\n")

    # --- Step 1: Load or generate frame ---
    print("Step 1: Loading examination frame...")
    from pathlib import Path
    frame_path = Path("data/mock/exam_frame.jpg")
    if frame_path.exists():
        import cv2
        frame = cv2.imread(str(frame_path))
        print(f"  Loaded: {frame_path} ({frame.shape[1]}x{frame.shape[0]})")
    else:
        print("  Generating synthetic frame...")
        from scripts.generate_mock_data import generate_exam_frame
        frame = generate_exam_frame(1920, 1080)
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        import cv2
        cv2.imwrite(str(frame_path), frame)
        print(f"  Generated: {frame_path} ({frame.shape[1]}x{frame.shape[0]})")
    print()

    # --- Step 2: Define student ROI ---
    print("Step 2: Defining student/desk ROI...")
    track_id = "T17"
    seat_id = "B4"
    roi = [720, 300, 1080, 780]
    print(f"  Track: {track_id}")
    print(f"  Seat: {seat_id}")
    print(f"  ROI: {roi} (original frame coordinates)")
    print()

    # --- Step 3: Crop ROI from ORIGINAL frame ---
    print("Step 3: Cropping ROI from original high-resolution frame...")
    from app.roi.cropper import ROICropper
    cropper = ROICropper(detector_input_size=640)
    crop, validated_roi = cropper.crop(frame, roi, resize_to_detector=False)
    print(f"  Original frame: {frame.shape[1]}x{frame.shape[0]}")
    print(f"  ROI crop: {crop.shape[1]}x{crop.shape[0]} original pixels")
    info = cropper.get_crop_info(frame.shape, roi)
    print(f"  Frame coverage: {info['frame_coverage']*100:.1f}%")
    print()

    # --- Step 4: Image quality analysis ---
    print("Step 4: Image quality analysis...")
    from app.roi.quality import ImageQualityAnalyzer, CLAHEPreprocessor
    quality_analyzer = ImageQualityAnalyzer()
    img_quality = quality_analyzer.analyze(crop)
    print(f"  Quality score: {img_quality.image_quality:.2f}")
    print(f"  Contrast: {img_quality.contrast_quality:.2f}")
    print(f"  Overexposure: {img_quality.overexposure}")
    print(f"  Blur score: {img_quality.blur_score:.2f}")

    clahe = CLAHEPreprocessor()
    crop, img_quality = clahe.process(crop, img_quality)
    print(f"  CLAHE applied: {img_quality.clahe_applied}")
    print()

    # --- Step 5: Run YOLO26-S detection ---
    print("Step 5: Running YOLO26-S object detection...")
    detector_input = cropper._resize_for_detector(crop)
    detector = registry.get_detector("live")
    detections = detector.predict(
        detector_input,
        confidence_threshold=settings.default_object_confidence,
        trigger="HAND_OUTSIDE_DESK",
    )
    print(f"  Detections: {len(detections)}")
    for det in detections:
        print(f"    - {det.object_class}: {det.confidence:.2f} bbox={det.bbox}")
    print()

    # --- Step 6: Temporal smoothing ---
    print("Step 6: Temporal evidence smoothing...")
    from app.roi.temporal import TemporalSmoother
    smoother = TemporalSmoother()

    # Simulate 5 frames of detections
    sim_confs = [0.31, 0.42, 0.81, 0.91, 0.94]
    for i, conf in enumerate(sim_confs):
        smoothed, ready = smoother.update(track_id, "mobile_phone", conf)
        print(f"  Frame {i+1}: raw={conf:.2f} -> smoothed={smoothed:.2f} evidence_ready={ready}")
    print()

    # --- Step 7: Generate live evidence ---
    print("Step 7: Generating live evidence...")
    from app.verification.evidence import EvidenceGenerator
    evidence_gen = EvidenceGenerator()

    live_evidence = evidence_gen.create_live_evidence(
        track_id=track_id,
        camera_id="CAM_01",
        timestamp=time.time(),
        detections=detections,
        seat_id=seat_id,
        image_quality=img_quality.image_quality,
        trigger_events=["HAND_OUTSIDE_DESK"],
    )
    live_risk = max((d.confidence for d in detections), default=0.0)
    print(f"  Alert ID: {live_evidence.alert_id}")
    print(f"  Live risk: {live_risk:.2f}")
    print()

    # --- Step 8: Simulated retrospective verification ---
    print("Step 8: Running retrospective verification (simulated)...")

    # Temporal scanning with VideoMAE V2-L
    temporal_verifier = registry.get_temporal_verifier("videomae")
    mock_frames = [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8) for _ in range(32)]
    mock_timestamps = [642.0 + i * 0.3 for i in range(32)]
    temporal_windows = temporal_verifier.analyze(mock_frames, mock_timestamps)

    # Find most suspicious window
    best_window = max(temporal_windows, key=lambda w: w.temporal_anomaly_score)
    print(f"  Temporal windows scanned: {len(temporal_windows)}")
    print(f"  Most suspicious: {best_window.window_start:.1f}s-{best_window.window_end:.1f}s")
    print(f"  Temporal anomaly score: {best_window.temporal_anomaly_score:.2f}")

    # High-accuracy verification with RT-DETR + ViTPose
    ha_detector = registry.get_high_accuracy_detector("rtdetr")
    ha_detections = ha_detector.predict(crop, confidence_threshold=0.3)
    print(f"  RT-DETR detections: {len(ha_detections)}")
    for det in ha_detections:
        print(f"    - {det.object_class}: {det.confidence:.2f}")

    pose_verifier = registry.get_pose_verifier("vitpose")
    pose = pose_verifier.predict(crop)
    print(f"  Pose confidence: {pose.pose_confidence:.2f}")
    print(f"  Head direction: {pose.head_direction}")
    print(f"  Hand visibility: {pose.hand_visibility:.2f}")
    print()

    # --- Step 9: Compare live vs retrospective ---
    print("Step 9: Comparing live vs retrospective results...")
    from app.verification.comparator import LiveRetroComparator
    comparator = LiveRetroComparator()

    verified_risk = max((d.confidence for d in ha_detections), default=0.0) * 0.7 + best_window.temporal_anomaly_score * 0.3

    comparison = comparator.compare(
        live_risk=live_risk,
        verified_risk=verified_risk,
        live_detections=detections,
        verified_detections=ha_detections,
        temporal_anomaly_score=best_window.temporal_anomaly_score,
    )
    print(f"  Live risk: {comparison['live_risk']:.2f}")
    print(f"  Verified risk: {comparison['verified_risk']:.2f}")
    print(f"  Status: {comparison['verification_status'].value}")
    print()

    # --- Step 10: Final evidence JSON ---
    print("=" * 60)
    print("LIVE RESULT")
    print("-" * 60)
    print(f"Track: {track_id}")
    for det in detections:
        print(f"Object: {det.object_class}")
        print(f"Confidence: {det.confidence:.2f}")
    print()

    print("RETROSPECTIVE RESULT")
    print("-" * 60)
    print(f"Temporal anomaly: {best_window.temporal_anomaly_score:.2f}")
    if ha_detections:
        print(f"Object verification: {max(d.confidence for d in ha_detections):.2f}")
    print(f"Pose verification: {pose.pose_confidence:.2f}")
    print()

    print("FINAL STATUS")
    print("-" * 60)
    print(comparison["verification_status"].value)
    print()

    # Full evidence JSON
    final_evidence = {
        "alert_id": live_evidence.alert_id,
        "track_ids": [track_id],
        "camera_id": "CAM_01",
        "seat_ids": [seat_id],
        "time_window": comparator.format_time_window(
            best_window.window_start, best_window.window_end
        ),
        "start_time": best_window.window_start,
        "end_time": best_window.window_end,
        "live_risk": comparison["live_risk"],
        "verified_risk": comparison["verified_risk"],
        "verification_status": comparison["verification_status"].value,
        "temporal_anomaly_score": best_window.temporal_anomaly_score,
        "objects": [d.model_dump() for d in detections + ha_detections],
        "pose_confidence": pose.pose_confidence,
        "image_quality": img_quality.image_quality,
        "human_review_required": True,
    }

    print("EVIDENCE JSON")
    print("-" * 60)
    print(json.dumps(final_evidence, indent=2))
    print()

    # Save to database so dashboard can pick it up
    import asyncio
    from app.storage import database as db
    
    async def save_to_db():
        await db.init_database(settings.database_path)
        await db.save_evidence(final_evidence)
        await db.close_database()

    asyncio.run(save_to_db())
    print("Saved evidence to database.")
    
    print("=" * 60)
    print("  [!] Human review required.")
    print("  This system produces evidence, not verdicts.")
    print("=" * 60)


if __name__ == "__main__":
    main()
