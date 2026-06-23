# DroneDetection Demo Assets

These assets package the current shipped/demo state of the project for presentation.

## Simulation Videos

- `follow_tracking_demo.mp4` - fast follow behavior toward a tracked drone target.
- `orbit_tracking_demo.mp4` - orbit-style path around the tracked target.
- `standoff_tracking_demo.mp4` - safer follow behavior that keeps a visible distance.

GIF versions are included for README previews or platforms that do not play MP4 inline.

## PCB Files

- `SP350_PCB_fabrication.zip` - manufacturer-ready Gerber/drill package for the drone-frame PCB.
- `Turret_Control_PCB_fabrication.zip` - manufacturer-ready Gerber/drill package for the turret controller PCB.
- `sp350_fc_compact.svg` - visual preview of the drone-frame board.
- `turret_control.svg` - visual preview of the turret controller board.

Both PCBs currently pass KiCad DRC with 0 violations and 0 unconnected pads. The turret PCB includes a labeled 12V-to-8.4V buck/BEC module footprint for the servo power rail.
