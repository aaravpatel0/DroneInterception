from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

from serial_controller import PicoSerialController


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path(__file__).resolve().parent / "camera_config.yaml"
PRODUCTION_MODEL = PROJECT_ROOT / "models" / "production_drone_model.pt"
FALLBACK_MODEL = PROJECT_ROOT / "models" / "drone_roboflow_best.pt"


@dataclass
class TrackerConfig:
    source: str
    port: str | None
    baud: int
    model: Path
    conf: float
    deadband_x: int
    deadband_y: int
    kp_pan: float
    kp_pan_right: float
    kp_tilt: float
    max_pan_step: int
    max_pan_step_right: int
    min_pan_step: int
    tilt_min: int
    tilt_max: int
    tilt_start: int
    x_deadband_inches: float
    y_deadband_inches: float
    show: bool
    dry_run: bool
    no_detection_stop_frames: int
    command_interval: float
    device: str | None
    drone_visible_width_inches: float
    drone_height_inches: float
    focal_length_px: float | None
    camera_horizontal_fov_deg: float
    camera_matrix: list[list[float]] | None
    dist_coeffs: list[float] | None
    calibration_image_size: list[int] | None
    position_output: Path | None
    tracking_log: Path | None
    prediction_horizon_sec: float
    max_prediction_step_inches: float
    lost_target_hold_sec: float
    prediction_alpha: float
    velocity_alpha: float
    imgsz: int
    console_log_interval: float

@dataclass
class DronePositionEstimate:
    distance_inches: float
    x_inches: float
    y_inches: float
    z_inches: float
    yaw_deg: float
    pitch_deg: float


@dataclass
class MotionEstimate:
    vx_inches_per_sec: float
    vy_inches_per_sec: float
    vz_inches_per_sec: float
    predicted_x_inches: float
    predicted_y_inches: float
    predicted_z_inches: float


@dataclass
class PredictionFilter:
    position: DronePositionEstimate
    motion: MotionEstimate | None
    updated_at: float


def project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_source(source: str) -> str | int:
    clean = str(source).strip()
    return int(clean) if clean.isdigit() else clean


def normalize_yolo_device(device: str | None) -> str | None:
    if device is None:
        return None
    clean = str(device).strip()
    return None if clean.lower() in {"", "auto"} else clean


def load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_model(model_arg: str | None) -> Path:
    if model_arg:
        requested = project_path(model_arg)
        if requested.exists():
            return requested
        if requested == PRODUCTION_MODEL and FALLBACK_MODEL.exists():
            print(f"[tracker] Production model missing, falling back to: {FALLBACK_MODEL}")
            return FALLBACK_MODEL
        raise FileNotFoundError(f"Model file not found: {requested}")
    if PRODUCTION_MODEL.exists():
        return PRODUCTION_MODEL
    if FALLBACK_MODEL.exists():
        print(f"[tracker] Production model missing, falling back to: {FALLBACK_MODEL}")
        return FALLBACK_MODEL
    raise FileNotFoundError(
        f"No model found. Place production model at {PRODUCTION_MODEL} "
        f"or fallback model at {FALLBACK_MODEL}."
    )


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def scale_camera_matrix(camera_matrix: np.ndarray, calibration_size: list[int] | None, frame_width: int, frame_height: int) -> np.ndarray:
    if not calibration_size or len(calibration_size) != 2:
        return camera_matrix
    source_width, source_height = float(calibration_size[0]), float(calibration_size[1])
    if source_width <= 0 or source_height <= 0:
        return camera_matrix
    scaled = camera_matrix.copy()
    scaled[0, 0] *= frame_width / source_width
    scaled[1, 1] *= frame_height / source_height
    scaled[0, 2] *= frame_width / source_width
    scaled[1, 2] *= frame_height / source_height
    return scaled

def focal_length_for_frame(frame_width: int, frame_height: int, config: TrackerConfig) -> float:
    if config.focal_length_px and config.calibration_image_size and len(config.calibration_image_size) == 2:
        return float(config.focal_length_px) * frame_width / float(config.calibration_image_size[0])
    if config.focal_length_px:
        return float(config.focal_length_px)
    return (frame_width / 2.0) / math.tan(math.radians(config.camera_horizontal_fov_deg) / 2.0)

def pixel_error_from_position(position: DronePositionEstimate, frame_width: int, frame_height: int, config: TrackerConfig) -> tuple[int, int]:
    focal_px = focal_length_for_frame(frame_width, frame_height, config)
    safe_z = max(1.0, abs(position.z_inches))
    return (
        int(round(focal_px * position.x_inches / safe_z)),
        int(round(-focal_px * position.y_inches / safe_z)),
    )

def position_distance_inches(a: DronePositionEstimate, b: DronePositionEstimate) -> float:
    dx = a.x_inches - b.x_inches
    dy = a.y_inches - b.y_inches
    dz = a.z_inches - b.z_inches
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def blend_position(previous: DronePositionEstimate, measured: DronePositionEstimate, alpha: float) -> DronePositionEstimate:
    blend = clamp(alpha, 0.0, 1.0)
    keep = 1.0 - blend
    x_inches = previous.x_inches * keep + measured.x_inches * blend
    y_inches = previous.y_inches * keep + measured.y_inches * blend
    z_inches = max(1.0, previous.z_inches * keep + measured.z_inches * blend)
    return DronePositionEstimate(
        distance_inches=z_inches,
        x_inches=x_inches,
        y_inches=y_inches,
        z_inches=z_inches,
        yaw_deg=measured.yaw_deg,
        pitch_deg=measured.pitch_deg,
    )

def undistort_frame(frame, config: TrackerConfig):
    if not config.camera_matrix or not config.dist_coeffs:
        return frame
    frame_height, frame_width = frame.shape[:2]
    camera_matrix = scale_camera_matrix(np.array(config.camera_matrix, dtype=np.float32), config.calibration_image_size, frame_width, frame_height)
    dist_coeffs = np.array(config.dist_coeffs, dtype=np.float32)
    return cv2.undistort(frame, camera_matrix, dist_coeffs)

def estimate_drone_position(
    box,
    frame_width: int,
    frame_height: int,
    config: TrackerConfig,
) -> DronePositionEstimate | None:
    if config.drone_visible_width_inches <= 0 or config.drone_height_inches <= 0:
        return None
    if config.camera_horizontal_fov_deg <= 0 or config.camera_horizontal_fov_deg >= 180:
        return None
    x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    focal_px = focal_length_for_frame(frame_width, frame_height, config)
    distance_from_width = config.drone_visible_width_inches * focal_px / box_width
    distance_inches = distance_from_width
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    yaw_rad = math.atan((center_x - frame_width / 2.0) / focal_px)
    pitch_rad = math.atan((frame_height / 2.0 - center_y) / focal_px)
    return DronePositionEstimate(
        distance_inches=distance_inches,
        x_inches=distance_inches * math.tan(yaw_rad),
        y_inches=distance_inches * math.tan(pitch_rad),
        z_inches=distance_inches,
        yaw_deg=math.degrees(yaw_rad),
        pitch_deg=math.degrees(pitch_rad),
    )


def best_drone_box(result, conf_threshold: float):
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return None

    best = None
    best_conf = -1.0
    # The turret follows one target at a time, so choose the most confident
    # drone box instead of averaging multiple detections.
    for box in boxes:
        class_id = int(box.cls[0].item()) if box.cls is not None else 0
        confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
        if class_id != 0 or confidence < conf_threshold:
            continue
        if confidence > best_conf:
            best = box
            best_conf = confidence
    return best


def draw_overlay(
    frame,
    box,
    confidence: float | None,
    error_x: int | None,
    error_y: int | None,
    pan_step: int,
    tilt_angle: int,
    conf_threshold: float,
    position: DronePositionEstimate | None,
    motion: MotionEstimate | None,
    focal_px: float,
) -> None:
    height, width = frame.shape[:2]
    frame_center = (width // 2, height // 2)
    cv2.drawMarker(frame, frame_center, (255, 255, 255), cv2.MARKER_CROSS, 24, 2)

    if box is not None:
        x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
        target_center = ((x1 + x2) // 2, (y1 + y2) // 2)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.drawMarker(frame, target_center, (0, 255, 255), cv2.MARKER_CROSS, 20, 2)
        cv2.line(frame, frame_center, target_center, (0, 255, 255), 1)
        if position is not None and motion is not None:
            safe_z = max(1.0, motion.predicted_z_inches)
            predicted_x = int(round(frame_center[0] + focal_px * motion.predicted_x_inches / safe_z))
            predicted_y = int(round(frame_center[1] - focal_px * motion.predicted_y_inches / safe_z))
            predicted_point = (
                int(clamp(predicted_x, 0, width - 1)),
                int(clamp(predicted_y, 0, height - 1)),
            )
            cv2.arrowedLine(frame, target_center, predicted_point, (255, 0, 255), 2, tipLength=0.25)
            cv2.drawMarker(frame, predicted_point, (255, 0, 255), cv2.MARKER_DIAMOND, 18, 2)
        cv2.putText(
            frame,
            f"drone {confidence:.2f}" if confidence is not None else "drone",
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

    text_lines = [
        f"conf >= {conf_threshold:.2f}",
        f"err x/y: {error_x if error_x is not None else '-'} / {error_y if error_y is not None else '-'}",
        f"cmd pan: {pan_step}  tilt: {tilt_angle}",
        f"focal px: {focal_px:.1f}",
        (
            f"angle yaw/pitch: {position.yaw_deg:.1f} / {position.pitch_deg:.1f} deg"
            if position is not None
            else "angle yaw/pitch: - / - deg"
        ),
        "keys: q quit | h home | s stop | +/- conf",
    ]
    for index, text in enumerate(text_lines):
        cv2.putText(
            frame,
            text,
            (12, 28 + index * 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
        )
    metric_lines = [
        ("camera origin: CAMERA = (0.0, 0.0, 0.0) in", (255, 255, 255)),
        (f"drone x from camera: {position.x_inches:.1f} in" if position else "drone x from camera: - in", (0, 0, 255)),
        (f"drone y from camera: {position.y_inches:.1f} in" if position else "drone y from camera: - in", (0, 255, 0)),
        (f"drone z from camera: {position.z_inches:.1f} in" if position else "drone z from camera: - in", (255, 0, 0)),
    ]
    for offset, (text, color) in enumerate(metric_lines):
        cv2.putText(frame, text, (12, 148 + offset * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2)


def send_or_print(controller: PicoSerialController | None, command: str, dry_run: bool, expect_response: bool = True) -> None:
    if dry_run:
        print(f"[dry-run] {command}")
        return
    if controller is None:
        return
    response = controller.send_command(command, expect_response=expect_response)
    if response.response:
        print(f"[pico2] {response.response}")


def reset_pico_pan_counter(controller: PicoSerialController | None, dry_run: bool) -> None:
    send_or_print(controller, "PANZERO", dry_run)
    if dry_run or controller is None:
        return
    status = controller.status()
    if status.response:
        print(f"[pico2] {status.response}")


def make_motion(position: DronePositionEstimate, vx: float, vy: float, vz: float, horizon_sec: float) -> MotionEstimate:
    return MotionEstimate(
        vx_inches_per_sec=vx,
        vy_inches_per_sec=vy,
        vz_inches_per_sec=vz,
        predicted_x_inches=position.x_inches + vx * horizon_sec,
        predicted_y_inches=position.y_inches + vy * horizon_sec,
        predicted_z_inches=max(1.0, position.z_inches + vz * horizon_sec),
    )


def update_prediction_filter(
    current_filter: PredictionFilter | None,
    measured: DronePositionEstimate,
    now: float,
    config: TrackerConfig,
) -> PredictionFilter:
    if current_filter is None:
        return PredictionFilter(position=measured, motion=None, updated_at=now)

    dt = max(0.001, now - current_filter.updated_at)
    jump_limit = max(6.0, config.max_prediction_step_inches * max(1.0, dt / max(0.001, config.prediction_horizon_sec)))
    if position_distance_inches(current_filter.position, measured) > jump_limit * 3.0:
        measured = blend_position(current_filter.position, measured, 0.15)

    filtered_position = blend_position(current_filter.position, measured, config.prediction_alpha)
    raw_vx = (filtered_position.x_inches - current_filter.position.x_inches) / dt
    raw_vy = (filtered_position.y_inches - current_filter.position.y_inches) / dt
    raw_vz = (filtered_position.z_inches - current_filter.position.z_inches) / dt

    if current_filter.motion is None:
        vx, vy, vz = raw_vx, raw_vy, raw_vz
    else:
        velocity_blend = clamp(config.velocity_alpha, 0.0, 1.0)
        keep = 1.0 - velocity_blend
        vx = current_filter.motion.vx_inches_per_sec * keep + raw_vx * velocity_blend
        vy = current_filter.motion.vy_inches_per_sec * keep + raw_vy * velocity_blend
        vz = current_filter.motion.vz_inches_per_sec * keep + raw_vz * velocity_blend

    motion = make_motion(filtered_position, vx, vy, vz, config.prediction_horizon_sec)
    motion = clamp_prediction_step(filtered_position, motion, config.max_prediction_step_inches)
    return PredictionFilter(position=filtered_position, motion=motion, updated_at=now)


def clamp_prediction_step(position: DronePositionEstimate, motion: MotionEstimate, max_step_inches: float) -> MotionEstimate:
    dx = motion.predicted_x_inches - position.x_inches
    dy = motion.predicted_y_inches - position.y_inches
    dz = motion.predicted_z_inches - position.z_inches
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if max_step_inches <= 0 or distance <= max_step_inches:
        return motion
    scale = max_step_inches / distance
    return MotionEstimate(
        vx_inches_per_sec=motion.vx_inches_per_sec,
        vy_inches_per_sec=motion.vy_inches_per_sec,
        vz_inches_per_sec=motion.vz_inches_per_sec,
        predicted_x_inches=position.x_inches + dx * scale,
        predicted_y_inches=position.y_inches + dy * scale,
        predicted_z_inches=position.z_inches + dz * scale,
    )


def predict_position_from_motion(position: DronePositionEstimate, motion: MotionEstimate, dt: float) -> DronePositionEstimate:
    return DronePositionEstimate(
        distance_inches=max(1.0, position.distance_inches + motion.vz_inches_per_sec * dt),
        x_inches=position.x_inches + motion.vx_inches_per_sec * dt,
        y_inches=position.y_inches + motion.vy_inches_per_sec * dt,
        z_inches=max(1.0, position.z_inches + motion.vz_inches_per_sec * dt),
        yaw_deg=position.yaw_deg,
        pitch_deg=position.pitch_deg,
    )


def apply_minimum_step(step: int, minimum: int) -> int:
    if step == 0 or minimum <= 0:
        return step
    if abs(step) >= minimum:
        return step
    return minimum if step > 0 else -minimum


def write_position(path: Path | None, position: DronePositionEstimate | None, motion: MotionEstimate | None) -> None:
    if path is None or position is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": time.time(),
        "origin": "camera",
        "camera_origin_inches": {"x": 0.0, "y": 0.0, "z": 0.0},
        **position.__dict__,
    }
    if motion is not None:
        payload.update(motion.__dict__)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    for attempt in range(5):
        try:
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                print(f"[tracker] Skipping position update because Windows locked {path.name}.")
                return
            time.sleep(0.02)


def open_tracking_log(path: Path | None):
    if path is None:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    log_file = path.open("w", encoding="utf-8", buffering=1)
    log_file.write(
        "time_unix,elapsed_ms,loop_ms,detected,confidence,"
        "x_inches,y_inches,z_inches,target_x_inches,target_y_inches,target_z_inches,"
        "pan_step,tilt_angle,error_x,error_y\n"
    )
    return log_file


def fmt_optional(value: float | int | None) -> str:
    return "" if value is None else str(value)


def fmt_signed(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:+.{digits}f}"
    return f"{value:+d}"


def log_tracking_row(
    log_file,
    start_time: float,
    loop_start: float,
    detected: bool,
    confidence: float | None,
    position: DronePositionEstimate | None,
    target_position: DronePositionEstimate | None,
    pan_step: int,
    tilt_angle: int,
    error_x: int | None,
    error_y: int | None,
) -> None:
    if log_file is None:
        return
    now = time.time()
    elapsed_ms = (time.monotonic() - start_time) * 1000.0
    loop_ms = (time.monotonic() - loop_start) * 1000.0
    values = [
        f"{now:.6f}",
        f"{elapsed_ms:.3f}",
        f"{loop_ms:.3f}",
        "1" if detected else "0",
        fmt_optional(None if confidence is None else round(confidence, 4)),
        fmt_optional(None if position is None else round(position.x_inches, 3)),
        fmt_optional(None if position is None else round(position.y_inches, 3)),
        fmt_optional(None if position is None else round(position.z_inches, 3)),
        fmt_optional(None if target_position is None else round(target_position.x_inches, 3)),
        fmt_optional(None if target_position is None else round(target_position.y_inches, 3)),
        fmt_optional(None if target_position is None else round(target_position.z_inches, 3)),
        str(pan_step),
        str(tilt_angle),
        fmt_optional(error_x),
        fmt_optional(error_y),
    ]
    log_file.write(",".join(values) + "\n")


def print_tracking_decision(
    detected: bool,
    confidence: float | None,
    position: DronePositionEstimate | None,
    target_position: DronePositionEstimate | None,
    error_x: int | None,
    error_y: int | None,
    pan_step: int,
    tilt_angle: int,
    sent_command: bool,
) -> None:
    state = "DETECT" if detected else ("PREDICT" if target_position is not None else "LOST")
    conf_text = "-" if confidence is None else f"{confidence:.2f}"
    pos_text = (
        f"x={fmt_signed(position.x_inches)}in y={fmt_signed(position.y_inches)}in z={position.z_inches:.1f}in"
        if position is not None
        else "x=- y=- z=-"
    )
    target_text = (
        f"target_x={fmt_signed(target_position.x_inches)}in target_y={fmt_signed(target_position.y_inches)}in"
        if target_position is not None
        else "target=-"
    )
    command_text = f"PAN {pan_step:+d} TILT {tilt_angle:d}" if sent_command else "hold"
    print(
        f"[track] {state:<7} conf={conf_text} "
        f"err=({fmt_signed(error_x, 0)},{fmt_signed(error_y, 0)}) "
        f"{pos_text} {target_text} -> pico2 {command_text}",
        flush=True,
    )


def run_tracker(config: TrackerConfig) -> None:
    model = YOLO(str(config.model))
    source = parse_source(config.source)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera/video source: {config.source}")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    controller: PicoSerialController | None = None
    if not config.dry_run:
        controller = PicoSerialController(port=config.port, baud=config.baud)
        controller.connect()
        print(f"[tracker] Connected to Pico 2 on {controller.port} at {config.baud}.")
    else:
        print("[tracker] Dry-run enabled; serial commands will be printed only.")

    tilt_angle = int(clamp(config.tilt_start, config.tilt_min, config.tilt_max))
    last_command_time = 0.0
    no_detection_frames = 0
    last_pan_step = 0
    last_position: DronePositionEstimate | None = None
    last_motion: MotionEstimate | None = None
    last_detection_time: float | None = None
    prediction_filter: PredictionFilter | None = None
    last_console_log_time = 0.0
    tracker_start_time = time.monotonic()
    log_file = open_tracking_log(config.tracking_log)

    try:
        reset_pico_pan_counter(controller, config.dry_run)
        while True:
            loop_start = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                print("[tracker] Source ended or frame read failed.")
                break
            frame = undistort_frame(frame, config)

            results = model.predict(
                frame,
                conf=config.conf,
                classes=[0],
                device=config.device,
                imgsz=config.imgsz,
                verbose=False,
            )
            result = results[0]
            box = best_drone_box(result, config.conf)
            error_x: int | None = None
            error_y: int | None = None
            confidence: float | None = None
            position: DronePositionEstimate | None = None
            motion: MotionEstimate | None = None
            target_position: DronePositionEstimate | None = None
            pan_step = 0
            sent_command = False
            live_detection = box is not None
            frame_height, frame_width = frame.shape[:2]

            now = time.monotonic()
            if box is None:
                no_detection_frames += 1
                if prediction_filter is not None and last_position is not None and last_detection_time is not None:
                    prediction_age = now - last_detection_time
                    if prediction_filter.motion is not None and prediction_age <= config.lost_target_hold_sec:
                        last_motion = prediction_filter.motion
                        target_position = predict_position_from_motion(last_position, last_motion, prediction_age)
                    elif prediction_age <= config.lost_target_hold_sec:
                        target_position = last_position
                    if target_position is not None:
                        error_x, error_y = pixel_error_from_position(target_position, frame_width, frame_height, config)
                if target_position is None:
                    if (
                        no_detection_frames == config.no_detection_stop_frames
                        and now - last_command_time >= config.command_interval
                    ):
                        send_or_print(controller, f"TILT {tilt_angle}", config.dry_run, expect_response=False)
                        last_command_time = now
                        sent_command = True
            else:
                no_detection_frames = 0
                x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
                confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
                position = estimate_drone_position(box, frame_width, frame_height, config)
                if position is not None:
                    prediction_filter = update_prediction_filter(prediction_filter, position, now, config)
                    motion = prediction_filter.motion
                    last_position = prediction_filter.position
                    last_motion = motion
                    last_detection_time = now
                    target_position = prediction_filter.position
                write_position(config.position_output, position, motion)
                box_center_x = int((x1 + x2) / 2)
                box_center_y = int((y1 + y2) / 2)
                error_x = box_center_x - frame_width // 2
                error_y = box_center_y - frame_height // 2

            if target_position is not None:
                if error_x is not None and abs(error_x) > config.deadband_x:
                    pan_step = int(clamp(config.kp_pan * error_x, -config.max_pan_step, config.max_pan_step))
                    pan_step = apply_minimum_step(pan_step, config.min_pan_step)
                if live_detection and abs(target_position.y_inches) > config.y_deadband_inches:
                    tilt_angle = int(round(clamp(tilt_angle + config.kp_tilt * target_position.y_inches, config.tilt_min, config.tilt_max)))

                if now - last_command_time >= config.command_interval:
                    # Rate-limit command bursts so detection jitter does not flood
                    # the Pico 2 serial buffer.
                    if pan_step:
                        send_or_print(controller, f"PAN {pan_step}", config.dry_run, expect_response=False)
                        last_pan_step = pan_step
                    send_or_print(controller, f"TILT {tilt_angle}", config.dry_run, expect_response=False)
                    last_command_time = now
                    sent_command = True

            if config.console_log_interval >= 0 and now - last_console_log_time >= config.console_log_interval:
                print_tracking_decision(
                    box is not None,
                    confidence,
                    position,
                    target_position,
                    error_x,
                    error_y,
                    pan_step,
                    tilt_angle,
                    sent_command,
                )
                last_console_log_time = now

            log_tracking_row(
                log_file,
                tracker_start_time,
                loop_start,
                box is not None,
                confidence,
                position,
                target_position,
                pan_step,
                tilt_angle,
                error_x,
                error_y,
            )

            if config.show:
                draw_overlay(
                    frame,
                    box,
                    confidence,
                    error_x,
                    error_y,
                    last_pan_step if pan_step == 0 else pan_step,
                    tilt_angle,
                    config.conf,
                    target_position,
                    last_motion,
                    focal_length_for_frame(frame_width, frame_height, config),
                )
                cv2.imshow("Drone Turret Tracker", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("h"):
                    tilt_angle = config.tilt_start
                    send_or_print(controller, "HOME", config.dry_run)
                if key == ord("s"):
                    send_or_print(controller, "STOP", config.dry_run)
                if key in (ord("+"), ord("=")):
                    config.conf = min(0.95, config.conf + 0.05)
                if key in (ord("-"), ord("_")):
                    config.conf = max(0.05, config.conf - 0.05)
    finally:
        try:
            send_or_print(controller, "STOP", config.dry_run)
        except Exception as exc:
            print(f"[tracker] STOP failed during shutdown: {exc}")
        if controller:
            controller.close()
        if log_file:
            log_file.close()
        cap.release()
        if config.show:
            cv2.destroyAllWindows()


def build_config(args: argparse.Namespace) -> TrackerConfig:
    file_config = load_yaml_config(Path(args.config))
    model_arg = args.model if args.model is not None else file_config.get("model_path")
    return TrackerConfig(
        source=str(args.source if args.source is not None else file_config.get("source", 0)),
        port=args.port if args.port is not None else file_config.get("port"),
        baud=int(args.baud if args.baud is not None else file_config.get("baud", 115200)),
        model=resolve_model(model_arg),
        conf=float(args.conf if args.conf is not None else file_config.get("confidence_threshold", 0.35)),
        deadband_x=int(args.deadband_x if args.deadband_x is not None else file_config.get("deadband_x", 40)),
        deadband_y=int(args.deadband_y if args.deadband_y is not None else file_config.get("deadband_y", 30)),
        kp_pan=float(args.kp_pan if args.kp_pan is not None else file_config.get("kp_pan", 0.03)),
        kp_pan_right=float(args.kp_pan_right if args.kp_pan_right is not None else file_config.get("kp_pan_right", args.kp_pan if args.kp_pan is not None else file_config.get("kp_pan", 0.03))),
        kp_tilt=float(args.kp_tilt if args.kp_tilt is not None else file_config.get("kp_tilt", 0.02)),
        max_pan_step=int(args.max_pan_step if args.max_pan_step is not None else file_config.get("max_pan_step", 30)),
        max_pan_step_right=int(args.max_pan_step_right if args.max_pan_step_right is not None else file_config.get("max_pan_step_right", args.max_pan_step if args.max_pan_step is not None else file_config.get("max_pan_step", 30))),
        min_pan_step=int(args.min_pan_step if args.min_pan_step is not None else file_config.get("min_pan_step", 0)),
        tilt_min=int(args.tilt_min if args.tilt_min is not None else file_config.get("tilt_min", 40)),
        tilt_max=int(args.tilt_max if args.tilt_max is not None else file_config.get("tilt_max", 140)),
        tilt_start=int(args.tilt_start if args.tilt_start is not None else file_config.get("tilt_start", 90)),
        x_deadband_inches=float(args.x_deadband_inches if args.x_deadband_inches is not None else file_config.get("x_deadband_inches", 1.0)),
        y_deadband_inches=float(args.y_deadband_inches if args.y_deadband_inches is not None else file_config.get("y_deadband_inches", 1.0)),
        show=bool(args.show),
        dry_run=bool(args.dry_run),
        no_detection_stop_frames=int(args.no_detection_stop_frames),
        command_interval=float(args.command_interval),
        device=normalize_yolo_device(args.device),
        drone_visible_width_inches=float(
            args.drone_visible_width_inches
            if args.drone_visible_width_inches is not None
            else file_config.get("drone_visible_width_inches", file_config.get("drone_diagonal_inches", 10.5))
        ),
        drone_height_inches=float(
            args.drone_height_inches
            if args.drone_height_inches is not None
            else file_config.get("drone_height_inches", 2.5)
        ),
        focal_length_px=(
            float(args.focal_length_px)
            if args.focal_length_px is not None
            else file_config.get("focal_length_px")
        ),
        camera_matrix=file_config.get("camera_matrix"),
        dist_coeffs=file_config.get("dist_coeffs"),
        calibration_image_size=file_config.get("calibration_image_size") or file_config.get("image_size"),
        position_output=Path(args.position_output) if args.position_output else None,
        tracking_log=Path(args.tracking_log) if args.tracking_log else None,
        prediction_horizon_sec=float(args.prediction_horizon_sec if args.prediction_horizon_sec is not None else file_config.get("prediction_horizon_sec", 0.75)),
        max_prediction_step_inches=float(args.max_prediction_step_inches if args.max_prediction_step_inches is not None else file_config.get("max_prediction_step_inches", 36.0)),
        lost_target_hold_sec=float(args.lost_target_hold_sec if args.lost_target_hold_sec is not None else file_config.get("lost_target_hold_sec", 0.75)),
        prediction_alpha=float(args.prediction_alpha if args.prediction_alpha is not None else file_config.get("prediction_alpha", 0.55)),
        velocity_alpha=float(args.velocity_alpha if args.velocity_alpha is not None else file_config.get("velocity_alpha", 0.35)),
        imgsz=int(args.imgsz if args.imgsz is not None else file_config.get("imgsz", 416)),
        console_log_interval=float(args.console_log_interval if args.console_log_interval is not None else file_config.get("console_log_interval", 0.1)),
        camera_horizontal_fov_deg=float(
            args.camera_horizontal_fov_deg
            if args.camera_horizontal_fov_deg is not None
            else file_config.get("camera_horizontal_fov_deg", 57.2)
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live YOLOv8 visual drone tracking for a pan/tilt turret.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to camera/tracker YAML config.")
    parser.add_argument("--source", help="Camera index, video path, or stream URL.")
    parser.add_argument("--port", help="Pico 2 serial port, such as COM6. Omit to auto-detect.")
    parser.add_argument("--baud", type=int, help="Pico 2 serial baud rate.")
    parser.add_argument("--model", help="YOLO model path. Defaults to models/production_drone_model.pt.")
    parser.add_argument("--conf", type=float, help="Confidence threshold.")
    parser.add_argument("--deadband-x", type=int, help="Horizontal pixel deadband.")
    parser.add_argument("--deadband-y", type=int, help="Vertical pixel deadband.")
    parser.add_argument("--kp-pan", type=float, help="Pan proportional gain in steps per pixel.")
    parser.add_argument("--kp-pan-right", type=float, help="Right-side pan gain in steps per pixel.")
    parser.add_argument("--kp-tilt", type=float, help="Tilt proportional gain in degrees per pixel.")
    parser.add_argument("--max-pan-step", type=int, help="Maximum pan steps per command.")
    parser.add_argument("--max-pan-step-right", type=int, help="Maximum positive/right pan steps per command.")
    parser.add_argument("--min-pan-step", type=int, help="Minimum nonzero pan command used outside the X deadband.")
    parser.add_argument("--tilt-min", type=int, help="Minimum tilt servo angle.")
    parser.add_argument("--tilt-max", type=int, help="Maximum tilt servo angle.")
    parser.add_argument("--tilt-start", type=int, help="Startup tilt servo angle.")
    parser.add_argument("--x-deadband-inches", type=float, help="Stop pan correction when drone X distance is close to zero.")
    parser.add_argument("--y-deadband-inches", type=float, help="Stop tilt correction when drone Y distance is close to zero.")
    parser.add_argument("--show", action="store_true", help="Show live OpenCV preview window.")
    parser.add_argument("--dry-run", action="store_true", help="Do not open serial; print intended commands.")
    parser.add_argument("--no-detection-stop-frames", type=int, default=10, help="Send STOP after this many missed frames.")
    parser.add_argument("--command-interval", type=float, default=0.08, help="Minimum seconds between command bursts.")
    parser.add_argument("--device", default="auto", help="YOLO device: auto, cpu, 0, etc.")
    parser.add_argument("--drone-visible-width-inches", type=float, help="Known visible long-side width of the drone.")
    parser.add_argument("--drone-diagonal-inches", dest="drone_visible_width_inches", type=float, help="Alias for --drone-visible-width-inches.")
    parser.add_argument("--drone-height-inches", type=float, help="Known physical height of the drone.")
    parser.add_argument("--focal-length-px", type=float, help="Calibrated focal length in pixels.")
    parser.add_argument("--camera-horizontal-fov-deg", type=float, help="Camera horizontal field of view in degrees.")
    parser.add_argument("--position-output", help="Optional JSON file for the latest estimated drone position.")
    parser.add_argument("--tracking-log", help="Optional CSV file for per-frame tracking and turret command logs.")
    parser.add_argument("--prediction-horizon-sec", type=float, help="Seconds ahead to predict drone motion.")
    parser.add_argument("--max-prediction-step-inches", type=float, help="Clamp prediction arrow length to reject noisy jumps.")
    parser.add_argument("--lost-target-hold-sec", type=float, help="Keep steering toward the last logged/predicted target for this long after detection drops.")
    parser.add_argument("--prediction-alpha", type=float, help="Position smoothing alpha for camera-space prediction.")
    parser.add_argument("--velocity-alpha", type=float, help="Velocity smoothing alpha for camera-space prediction.")
    parser.add_argument("--imgsz", type=int, help="YOLO inference image size. Lower values reduce latency.")
    parser.add_argument("--console-log-interval", type=float, help="Seconds between readable terminal tracking logs. Use 0 for every frame.")
    return parser.parse_args()


def main() -> None:
    run_tracker(build_config(parse_args()))


if __name__ == "__main__":
    main()
