"""
Model Export Script — ONNX, TensorRT, OpenVINO.

Usage:
    python scripts/export_model.py --model runs/train/contraband/weights/best.pt --format onnx
    python scripts/export_model.py --model runs/train/contraband/weights/best.pt --format engine
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Export YOLO26-S to deployment format")
    parser.add_argument("--model", type=str, required=True, help="Model weights path")
    parser.add_argument("--format", type=str, default="onnx", choices=["onnx", "engine", "openvino", "torchscript"], help="Export format")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    parser.add_argument("--half", action="store_true", help="FP16 export")
    parser.add_argument("--dynamic", action="store_true", help="Dynamic axes (ONNX)")
    parser.add_argument("--simplify", action="store_true", default=True, help="Simplify ONNX")
    parser.add_argument("--device", type=str, default="0", help="Device")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics not installed.")
        sys.exit(1)

    print(f"Exporting: {args.model} → {args.format}")
    model = YOLO(args.model)
    path = model.export(
        format=args.format,
        imgsz=args.imgsz,
        half=args.half,
        dynamic=args.dynamic,
        simplify=args.simplify,
        device=args.device,
    )
    print(f"Exported to: {path}")


if __name__ == "__main__":
    main()
