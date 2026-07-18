# Changelog

All notable changes to this project will be documented in this file.

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
