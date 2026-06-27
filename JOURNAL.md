# Drone Interceptor Journal

## Project Summary

Drone Interceptor is the project where I tried to make a computer understand a flying object well enough to follow it with real hardware. It combines a YOLOv8 drone detector, live camera tracking, rough 3D position estimation, prediction, turret firmware, demo simulations, CAD, and custom PCB designs.

The idea started small: point a camera at a drone, detect it, and move a turret so the drone stays centered. As I kept building, it turned into a much bigger engineering project. I had to work through computer vision, camera calibration, serial control, stepper motor movement, servo tilt, drone controller signals, IMU and ESP32 experiments, simulations, and PCB layout.

This is my favorite project because it feels like a real journey instead of a single script. Every stage taught me something different, and the project slowly became more physical, more organized, and more complete.

## What I Built

- A YOLOv8-based drone detection pipeline.
- A live camera tracker that finds the drone in each frame.
- A camera-relative 3D position estimate for the tracked drone.
- A short-term prediction system that draws where the drone appears to be moving.
- Raspberry Pi Pico 2 firmware for pan/tilt turret control.
- Stepper motor ramping so the turret can move more smoothly.
- Servo tilt control for vertical aiming.
- Demo simulations for follow, orbit, and standoff behavior.
- A turret controller PCB with a servo power rail and cleaner wiring.
- A compact drone-frame PCB concept for a small SP350-style frame.
- Fabrication ZIPs, DRC reports, previews, and project documentation.

## Build Story

At the beginning, the project was mostly about computer vision. I wanted to see if I could train or use a model to detect a small drone from a live camera feed. Once detection worked, the next problem was making the detection useful. A bounding box by itself is cool, but it does not tell the turret what to do. I added camera calibration, estimated distance from the size of the drone in the frame, and converted that into a rough 3D position relative to the camera.

After that, I connected the software to hardware. The tracker sends simple commands to a Raspberry Pi Pico 2, and the Pico moves a stepper motor for pan and a servo for tilt. This was one of the first moments where the project felt real, because the code was no longer just drawing boxes on a screen. It was moving something on my desk.

The hardest part was the drone-control side. I originally tried to control a commercial drone by electronically injecting joystick-like signals into its controller. That meant measuring voltages, testing resistor and capacitor filters, figuring out how the joystick axes mapped to movement, and debugging why the controller did or did not respond. I got parts of it working, but it was fragile and messy because the original joystick circuitry was still attached to the board.

That is when the project pivoted. Instead of continuing to fight the commercial controller, I decided to design my own boards while reusing the small Snaptain SP350-style frame, motors, and propellers. That made the project feel cleaner and more intentional. The frame and motors become the mechanical base, while the electronics become something I can understand, document, and improve.

I also made simulations because I wanted people to understand the control ideas even before the final PCBs arrive. The follow, orbit, and safe standoff demos show how the tracking logic behaves in 3D space. They are useful for presentation, but they also helped me think through what the real hardware should eventually do.

## What Was Challenging

The hardest challenge was making real hardware match what the code expected. In software, a value can be perfectly centered or perfectly scaled. In hardware, the signal might sag, a joystick board might average two voltage sources together, a motor might stall, or a sensor might not respond until the right register is written.

Some specific challenges:

- Getting stable detection from a live camera feed.
- Estimating depth from a 2D bounding box.
- Preventing noisy depth estimates from making the prediction jump.
- Making the turret move quickly without overshooting or stalling.
- Understanding how the commercial drone controller interpreted joystick voltages.
- Debugging voltage drops caused by the original joystick circuit still being attached.
- Pivoting from a hacked controller to custom PCB designs.
- Keeping the repo organized enough that someone else can understand the project.

## What I Am Proud Of

I am proud that this became a complete engineering project, not just a demo. The repo has code, firmware, CAD links, PCB files, Gerbers, demo videos, and documentation. The turret tracking and depth perception system work, and the custom boards are ready for fabrication and testing.

I am also proud of the pivot. The commercial-controller approach taught me a lot, but it was not the cleanest final design. Switching to custom PCBs made the project stronger, even though it meant learning more and rethinking the hardware plan.

The best part is that every subsystem connects to the same idea: a computer sees something in the real world, estimates where it is, predicts where it is going, and moves physical hardware in response.

## Current Status

- Live drone detection is working.
- Turret pan/tilt tracking is working.
- 3D camera-relative position estimation is working.
- Prediction arrows and logs are working.
- Demo simulations are exported as videos and GIFs.
- Turret and drone-frame PCB fabrication files are included.
- Both PCB DRC reports show zero violations and zero unconnected pads.
- The next step is waiting for the PCBs, assembling them, and testing the hardware version.

## Next Steps

- Order or receive the fabricated PCBs.
- Assemble the turret controller board and verify power rails.
- Assemble the drone-frame PCB and test motor outputs carefully.
- Test the full tracker with the new boards.
- Tune movement gains after seeing real hardware behavior.
- Record final hardware demo footage once the PCBs are installed.

## Reflection

This project reminded me that building real things is messy in the best way. The path was not straight. I broke things, measured things, changed plans, rewired parts, redesigned boards, and kept turning confusing problems into smaller ones I could solve.

That is why it is my favorite project. It started as an idea on a screen and slowly became something with motors, wires, boards, videos, and a story.
