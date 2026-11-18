# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-11-18

### Added

- `docs/roboguide_setup.md`: step-by-step guide to control a ROBOGUIDE virtual ER-4iA from
  Ubuntu / ROS 2 Humble over Wi-Fi.
- `config/fanuc_moveit_controllers.yaml`: MoveIt `Ros2ControlManager` settings for the FANUC driver.
- `scripts/fanuc_connection_check.py`: read-only reachability check for RMI and Stream Motion.
- `scripts/er4ia_motion_check.py`: MoveIt plan-and-execute smoke test with PASS/FAIL.
- `scripts/fanuc_controller_emulator.py`: minimal RMI + Stream Motion stand-in for testing without ROBOGUIDE.
- `test/integration_test.sh` and `.github/workflows/integration.yml`: end-to-end tests that build the
  FANUC driver and move the robot with mock hardware and through the emulator.

### Changed

- `launch/fanuc_er4ia.launch.py` now follows FANUC's `fanuc_moveit_template.launch.py`. It uses
  FANUC's control launch files, so the hardware interface gets its GPIO configuration, the
  `ScaledJointTrajectoryController`, the correct update rate and controller spawning. Previously it
  started a plain 100 Hz `JointTrajectoryController` with no GPIO configuration, and that couldn't
  drive a ROBOGUIDE or real controller.
- Added the `fanuc_controllers`, `fanuc_moveit_config` and `moveit_ros_control_interface` runtime
  dependencies.

## [0.3.0] - 2026-07-18

### Changed

- Prepared the package for a public open-source release.
- Cleaned package metadata and dependency declarations.
- Reformatted launch, XML, YAML, and CMake files for readability.
- Added repository documentation, contribution guidance, and GitHub templates.
- Added GitHub Actions CI for ROS 2 Humble on Ubuntu 22.04.

### Fixed

- Replaced deprecated `load_yaml()` usage with `xacro.load_yaml()`.
- Corrected the SRDF virtual joint definition to avoid invalid `world -> world` static transforms.
- Updated demo and hardware-oriented launches to use the recommended `~/robot_description` remapping for `ros2_control`.
- Removed the controller deprecation warning by setting `allow_nonzero_velocity_at_trajectory_end: false`.
