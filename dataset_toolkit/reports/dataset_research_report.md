# Dataset Research Report

This report is generated from a manually curated research list. Downloaders use only official Git, Kaggle, Roboflow, or direct URLs and never bypass authentication or license gates.

## UETT4K Anti-UAV

- Dataset ID: `uett4k_anti_uav`
- Source: https://github.com/mugheessarwarawan/UETT4K-Anti-UAV.git
- Status: `manual_download_required`
- Download method: `git`
- Annotation format: Likely YOLO/images; inspect after download.
- Classes: drone
- Useful for: High-resolution small UAV detection in 4K imagery.
- Notes: Public GitHub source reports 33,601 images, but license terms should be reviewed before automated use.

## Anti-UAV Benchmark

- Dataset ID: `anti_uav_zhao`
- Source: https://github.com/ZhaoJ9014/Anti-UAV
- Status: `manual_download_required`
- Download method: `manual`
- Annotation format: Tracking JSON/TXT with bounding boxes and visibility flags.
- Classes: drone, negative/invisible frames
- Useful for: RGB/IR video tracking, small UAVs, challenging outdoor backgrounds.
- Notes: Official repo describes Full HD RGB/IR videos with dense boxes and existence flags; use official download links only.

## DUT Anti-UAV Detection and Tracking

- Dataset ID: `dut_anti_uav`
- Source: https://github.com/wangdongdut/DUT-Anti-UAV
- Status: `recommended`
- Download method: `manual`
- Annotation format: Detection/tracking ground truth; inspect exact files after download.
- Classes: drone
- Useful for: Anti-UAV detection/tracking benchmark with visible and thermal references.
- Notes: Good candidate if manual download links are accepted. Converter includes MOT/tracking TXT support.

## Drone Detection Dataset by Maciullo

- Dataset ID: `maciullo_drone_detection`
- Source: https://github.com/Maciullo/DroneDetectionDataset
- Status: `recommended`
- Download method: `manual`
- Annotation format: Pascal VOC XML
- Classes: drone, negative-like frames possible
- Useful for: Large visible-light drone images, varied sizes/backgrounds, XML labels.
- Notes: README reports 51,446 train and 5,375 test 640x480 RGB images with XML labels.

## YOLO Drone Detection Dataset

- Dataset ID: `kaggle_muki_yolo_drone`
- Source: https://www.kaggle.com/datasets/muki2003/yolo-drone-detection-dataset
- Status: `optional`
- Download method: `kaggle`
- Annotation format: YOLO txt
- Classes: drone
- Useful for: Ready YOLO drone detection images and labels.
- Notes: Search result reports 1,012 train and 347 validation images; license is not clean enough to mark as commercial-safe.

## Drone Detection

- Dataset ID: `kaggle_cybersimar_drone_detection`
- Source: https://www.kaggle.com/datasets/cybersimar08/drone-detection
- Status: `recommended`
- Download method: `kaggle`
- Annotation format: Bounding boxes; inspect CSV/XML/YOLO after download.
- Classes: drone
- Useful for: Permissive drone bounding-box data for detection/tracking.
- Notes: Kaggle page describes drone images with bounding boxes and CC0 license.

## Drone Object Detection

- Dataset ID: `kaggle_sshikamaru_drone_yolo`
- Source: https://www.kaggle.com/datasets/sshikamaru/drone-yolo-detection
- Status: `recommended`
- Download method: `kaggle`
- Annotation format: YOLO/Darknet txt
- Classes: drone, negative objects
- Useful for: 4,000+ amateur drone pictures plus drone-like negative objects.
- Notes: Useful for false positive reduction due to non-drone drone-like objects.

## Drone Dataset UAV

- Dataset ID: `kaggle_dasmehdixtr_drone_uav`
- Source: https://www.kaggle.com/datasets/dasmehdixtr/drone-dataset-uav
- Status: `optional`
- Download method: `kaggle`
- Annotation format: txt/xml labels reported; inspect after download.
- Classes: drone
- Useful for: Drone object detection images if license is acceptable.
- Notes: Included because several mirrors credit this source; verify dataset page and license.

## Bird vs Drone

- Dataset ID: `kaggle_stealthknight_bird_vs_drone`
- Source: https://www.kaggle.com/datasets/stealthknight/bird-vs-drone
- Status: `optional`
- Download method: `kaggle`
- Annotation format: YOLO segmentation/polygons or boxes; inspect after download.
- Classes: drone, bird
- Useful for: Reducing bird-vs-drone false positives.
- Notes: Use if license shown by Kaggle/Mendeley is acceptable for your target use.

## YOLO-based Segmented Dataset for Drone vs. Bird Detection

- Dataset ID: `mendeley_drone_vs_bird_seg`
- Source: https://data.mendeley.com/datasets/6ghdz52pd7/3
- Status: `recommended`
- Download method: `manual`
- Annotation format: YOLO segmentation polygons, convertible to boxes.
- Classes: drone, bird
- Useful for: Bird/drone separation and segmentation-to-box conversion.
- Notes: Mendeley search result reports 640x640 JPEG images and CC BY 4.0 license.

## Drones Detection with YOLOv8

- Dataset ID: `roboflow_zhejiang_drones_yolov8`
- Source: https://universe.roboflow.com/zhejiang-university-china-dliq1/drones-detection-with-yolov8
- Status: `optional`
- Download method: `roboflow`
- Annotation format: Roboflow YOLOv8 export
- Classes: drone
- Useful for: Ready YOLOv8-format drone data if export/license permits.
- Notes: Roboflow downloads should use the official API/export flow only.

## YOLO Drone Detection Dataset - Roboflow

- Dataset ID: `roboflow_ivonne_yolo_drone`
- Source: https://universe.roboflow.com/ivonne/yolo-drone-detection-dataset
- Status: `optional`
- Download method: `roboflow`
- Annotation format: Roboflow YOLOv8 export
- Classes: drone
- Useful for: Additional YOLO drone imagery if licensing is acceptable.
- Notes: Roboflow project/version identifiers may need manual confirmation.

## Incenda AI Aerospace Open Dataset

- Dataset ID: `incenda_aerospace_open`
- Source: https://www.incenda.ai/open-dataset/
- Status: `recommended`
- Download method: `manual`
- Annotation format: Pascal VOC XML and segmentation XML/PNG.
- Classes: drone, airplane, helicopter, hot_air_balloon, other
- Useful for: False-positive control and multi-class flying object detection.
- Notes: Page reports 500 frames and 837 objects, including drone, airplane and helicopter classes.

## Flying Object Detection from a Single Moving Camera

- Dataset ID: `epfl_flying_objects`
- Source: https://www.epfl.ch/labs/cvlab/research/uav/research-unmanned-detection/
- Status: `manual_download_required`
- Download method: `manual`
- Annotation format: Video/patch tracking annotations; inspect after download.
- Classes: uav, aircraft
- Useful for: Tiny flying objects filmed by moving cameras.
- Notes: Interesting for tracking, but license/access terms need manual confirmation.

## YOLOBirDrone / BirDrone

- Dataset ID: `yolobirdrone_2026`
- Source: https://arxiv.org/abs/2601.08319
- Status: `skip`
- Download method: `none`
- Annotation format: Unknown
- Classes: drone, bird
- Useful for: Potentially strong bird-vs-drone training data.
- Notes: Do not download until official data release and license are available.
