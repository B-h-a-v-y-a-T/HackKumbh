"""
YOLO26-S Fine-Tuning Script for exam contraband detection.

Classes: mobile_phone, paper_chit, prohibited_object

Usage:
    python scripts/train_yolo.py --data datasets/contraband/data.yaml --epochs 100
    python scripts/train_yolo.py --data datasets/contraband/data.yaml --epochs 50 --device cpu
    python scripts/train_yolo.py --resume runs/train/last.pt
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Train YOLO26-S for contraband detection")
    parser.add_argument("--data", type=str, default="datasets/contraband/data.yaml", help="Dataset YAML path")
    parser.add_argument("--model", type=str, default="yolo26s.pt", help="Base model weights")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", type=str, default="0", help="Device (0, cpu, mps)")
    parser.add_argument("--project", type=str, default="runs/train", help="Project directory")
    parser.add_argument("--name", type=str, default="contraband", help="Experiment name")
    parser.add_argument("--resume", type=str, default=None, help="Resume from checkpoint")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience")
    parser.add_argument("--workers", type=int, default=8, help="Dataloader workers")
    parser.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    parser.add_argument("--augment", action="store_true", default=True, help="Enable augmentation")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except ImportError:
        print("Error: ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    # Load model
    if args.resume:
        print(f"Resuming from: {args.resume}")
        model = YOLO(args.resume)
    else:
        print(f"Loading base model: {args.model}")
        model = YOLO(args.model)

    # Verify dataset
    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Dataset config not found: {data_path}")
        print("Create your dataset first. See datasets/contraband/README.md")
        sys.exit(1)

    print(f"\nTraining Configuration:")
    print(f"  Dataset: {args.data}")
    print(f"  Model: {args.model}")
    print(f"  Epochs: {args.epochs}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Batch size: {args.batch}")
    print(f"  Device: {args.device}")
    print(f"  Augmentation: {args.augment}")
    print()

    # Train
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
        workers=args.workers,
        lr0=args.lr0,
        augment=args.augment,
        save=True,
        save_period=10,
        val=True,
        plots=True,
        verbose=True,
    )

    print(f"\nTraining complete!")
    print(f"Best model: {args.project}/{args.name}/weights/best.pt")
    print(f"Last model: {args.project}/{args.name}/weights/last.pt")


if __name__ == "__main__":
    main()
