from __future__ import annotations

import platform
from pathlib import Path


def main() -> None:
    print(f"Python version: {platform.python_version()}")
    try:
        import torch

        print(f"torch version: {torch.__version__}")
        print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
        print(f"torch.version.cuda: {torch.version.cuda}")
        if torch.cuda.is_available():
            print(f"GPU name: {torch.cuda.get_device_name(0)}")
        else:
            print("GPU name: <none>")
    except Exception as exc:
        print(f"torch import/check failed: {exc}")

    try:
        import ultralytics  # noqa: F401

        print("ultralytics imports: True")
    except Exception as exc:
        print(f"ultralytics imports: False ({exc})")

    print(f"data/yolo/data.yaml exists: {Path('data/yolo/data.yaml').exists()}")
    print(f"models/drone_roboflow_best.pt exists: {Path('models/drone_roboflow_best.pt').exists()}")


if __name__ == "__main__":
    main()
