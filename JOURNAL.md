# Drone Interceptor Journal

This is my build journal for Drone Interceptor. I wanted it to feel like an honest record of the project: what I tried, what worked, what broke, and how the project slowly became real.

## Images

![SP350 drone-frame PCB preview](Drone%20PCB/preview/sp350_fc_compact.svg)

![Turret controller PCB preview](Turret%20Control%20PCB/preview/turret_control.svg)

## June 12, 2026

I organized the first version of the repo and started turning the project into something I could actually build on. I set up the dataset and YOLO training workflow, added scripts for cleaning and previewing labels, and started documenting how the detector would be trained.

This was the software foundation day. The project was still mostly about getting a drone detector working and making sure the code was not just scattered experiments.

## Mid-June 2026

I worked on the live tracking pipeline. The tracker used a camera feed, found the drone with YOLOv8, and started estimating where the drone was relative to the camera.

This is when the project started feeling less like "detect an object" and more like "understand where the object is." I added camera calibration, rough depth estimation, and the first version of the 3D position output.

## Late June 2026

I connected the tracker to physical hardware. The Raspberry Pi Pico 2 controlled the turret, with a stepper motor for pan and a servo for tilt. I tested serial commands, pan movement, tilt movement, and basic tracking behavior.

This was a big moment because the code was no longer just drawing boxes on a screen. It was moving real hardware.

## Drone Controller Experiments

I tried controlling a commercial drone through its controller by sending joystick-like signals from a Pico. I tested the joystick axis mapping, measured voltages, and debugged why some channels responded while others did not.

I learned that the original joystick circuit was still affecting the signals, which made the controller harder to control cleanly. Some tests worked, especially after changing resistor values and checking the voltages, but it was not reliable enough for the final version.

This part was frustrating, but it taught me a lot about real electronics. Software values are clean. Hardware values sag, average together, and behave differently once the actual circuit is connected.

## ESP32 And IMU Work

I also tested an ESP32-C3 with a BMI160 IMU. The goal was to track the drone-side position and orientation over WiFi and show that data in the 3D visualizer.

I changed the visualizer so the IMU could act as the zero point, with the camera and tracked drone shown relative to it. This helped connect the software map to the physical drone hardware idea.

## PCB Pivot

After enough testing with the hacked drone controller, I decided to pivot. Instead of fighting the commercial controller, I started designing custom PCBs while still reusing the small Snaptain SP350-style frame, motors, and propellers.

This made the project feel much cleaner. The drone frame and motors could stay, but the electronics could become something I actually understood and could improve.

I designed:

- A compact drone-frame PCB.
- A turret controller PCB.
- Fabrication ZIPs for both boards.
- PCB previews and DRC reports.

Both boards currently have DRC reports showing zero violations and zero unconnected pads.

## Simulation And Presentation

I made demo simulations for the tracking behavior so the project could still be shown clearly while waiting for the PCBs. The simulations show follow, orbit, and safe standoff behavior in 3D space.

These demos helped me explain the algorithm visually. They also made the project feel more complete because someone can understand the idea without needing the final hardware in front of them.

## June 23, 2026

I cleaned up the repo, organized the README, added demo links, added the CAD link, added PCB fabrication links, and prepared the project for shipping.

This was the day the project started feeling presentable instead of just functional. I wanted the repo to show the story and not just the files.

## June 26, 2026

I added this journal and wrote the ship materials. At this point, the software, simulations, firmware, CAD, and PCB files are all in place.

The next big step is physical assembly: waiting for the PCBs, soldering everything, checking power rails, and testing the full hardware version.

## What I Am Most Proud Of

I am most proud that this project became a complete system. It has vision, tracking, prediction, simulations, firmware, CAD, and PCB design all connected to one idea.

It is also my favorite project because the path was not perfect. I had to debug things, change plans, and make decisions when an approach was clearly too fragile. That made the final project feel more real.
