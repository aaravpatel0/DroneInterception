# YOLOv8 Drone Model Training Report

## Model Artifact

- Final checkpoint: `models/drone_roboflow_best.pt`
- Training run: `runs/train/drone_roboflow_yolov8`
- Base model: `yolov8n.pt`
- Task: object detection
- Classes: `drone`

The checkpoint is intentionally not tracked in git because model weights are binary artifacts. Store or distribute `models/drone_roboflow_best.pt` separately if the exact trained weights need to be shared.

## Dataset

- Source datasets: `Drone1`, `Drone2`, `Drone3`
- Merged data config: `data/yolo/data.yaml`
- Split ratios: 70% train, 15% validation, 15% test

## Training Parameters

| Parameter | Value |
| --- | --- |
| epochs | 50 |
| image size | 640 |
| batch size | 8 |
| device | CUDA device `0` |
| workers | 8 |
| pretrained | true |
| optimizer | auto |
| AMP | true |
| seed | 0 |
| deterministic | true |
| patience | 100 |
| initial learning rate | 0.01 |
| final LR factor | 0.01 |
| momentum | 0.937 |
| weight decay | 0.0005 |
| mosaic | 1.0 |
| flip left-right | 0.5 |
| translate | 0.1 |
| scale | 0.5 |

## Final Validation Metrics

From epoch 50 of `results.csv`:

| Metric | Value |
| --- | --- |
| precision | 0.93367 |
| recall | 0.91445 |
| mAP50 | 0.94803 |
| mAP50-95 | 0.63666 |
| train box loss | 1.04094 |
| train class loss | 0.48942 |
| train DFL loss | 1.15648 |
| validation box loss | 1.19633 |
| validation class loss | 0.53970 |
| validation DFL loss | 1.22269 |

## Held-Out Test Evaluation

From `data/processed/evaluation_report.txt`:

| Metric | Value |
| --- | --- |
| precision | 0.935996 |
| recall | 0.918033 |
| mAP50 | 0.950474 |
| mAP50-95 | 0.638715 |

## Notes

- Training used the Docker GPU path with PyTorch `2.11.0+cu128`.
- GPU detected during training: NVIDIA GeForce RTX 5070 Ti.
- Docker shared memory was increased for training stability with dataloader workers.
