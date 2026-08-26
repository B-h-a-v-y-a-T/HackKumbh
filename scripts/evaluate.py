"""
YOLO26-S Evaluation Script.

Usage:
    python scripts/evaluate.py --model runs/train/contraband/weights/best.pt
    python scripts/evaluate.py --model runs/train/contraband/weights/best.pt --data datasets/contraband/data.yaml
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Evaluate YOLO26-S contraband detector")
    parser.add_argument("--model", type=str, required=True, help="Model weights path")
    parser.add_argument("--data", type=str, default="datasets/contraband/data.yaml", help="Dataset config")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", type=str, default="0", help="Device")
    parser.add_argument("--split", type=str, default="test", help="Dataset split (val/test)")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.5, help="IoU threshold")
    parser.add_argument("--verbose", action="store_true", default=True)
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics not installed.")
        sys.exit(1)

    print(f"Evaluating: {args.model}")
    print(f"Dataset: {args.data} (split: {args.split})")
    print(f"Conf threshold: {args.conf}, IoU threshold: {args.iou}")
    print()

    model = YOLO(args.model)
    results = model.val(
        data=args.data,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        split=args.split,
        conf=args.conf,
        iou=args.iou,
        verbose=args.verbose,
        plots=True,
    )

    print(f"\nResults:")
    print(f"  mAP@50: {results.box.map50:.4f}")
    print(f"  mAP@50-95: {results.box.map:.4f}")
    print(f"  Precision: {results.box.mp:.4f}")
    print(f"  Recall: {results.box.mr:.4f}")
    print(f"\nPer-class mAP@50:")
    for i, name in enumerate(results.names.values()):
        print(f"  {name}: {results.box.ap50[i]:.4f}")


if __name__ == "__main__":
    main()
