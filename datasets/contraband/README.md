# Contraband Detection Dataset

## Classes

| ID | Class | Description |
|----|-------|-------------|
| 0 | mobile_phone | Phones on desk, in hand, partially hidden, near lap |
| 1 | paper_chit | Folded chits, partially visible, under hand |
| 2 | prohibited_object | Other prohibited items being passed or hidden |

## Annotation Format

YOLO format: `class_id x_center y_center width height` (normalized 0-1)

## Required Positive Examples

- Phone on desk, in hand, partially hidden, near lap
- Folded chit, partially visible, under hand
- Object being passed, near desk edge

## Required Hard Negatives

- Answer sheets, question papers, legitimate paper
- Pens, permitted calculators, books
- Desks, clothing, shadows, desk labels, bags

## Augmentation Strategy

Apply during training:
- Low light / brightness variation
- Glare and shadows
- Motion blur
- Different camera angles (rotation ±15°)
- Partial occlusion (cutout)
- Scale variation (different student distances)
- Mosaic augmentation

## Directory Structure

```
datasets/contraband/
  images/
    train/    # Training images
    val/      # Validation images
    test/     # Test images
  labels/
    train/    # Training labels (YOLO format .txt)
    val/      # Validation labels
    test/     # Test labels
  data.yaml   # Dataset configuration
```
