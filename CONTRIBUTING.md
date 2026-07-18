# Contributing

## Development Setup

1. Use Ubuntu 22.04 with ROS 2 Humble.
2. Place this package in a colcon workspace together with:
   - `fanuc_description`
   - `fanuc_driver`
3. Install dependencies with `rosdep`.

## Build

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select fanuc_er4ia_moveit_config
source install/setup.bash
```

## Validation

Before opening a pull request, run:

```bash
python3 -m compileall launch
colcon build --symlink-install --packages-select fanuc_er4ia_moveit_config
ros2 launch fanuc_er4ia_moveit_config demo.launch.py
```

Use `fanuc_er4ia.launch.py` when validating against the FANUC hardware interface stack.

## Style Guidelines

- Keep launch files readable and minimally stateful.
- Preserve robot behavior unless fixing a confirmed defect.
- Avoid introducing absolute filesystem paths.
- Keep package metadata, documentation, and CI in sync with functional changes.

## Pull Requests

- Describe the motivation and user-visible effect.
- Include validation steps and results.
- Add or update documentation when behavior changes.
