cmake_minimum_required(VERSION 3.8)
project(fanuc_er4ia_moveit_config)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}
  PATTERN "setup_assistant.launch.py" EXCLUDE
)

install(PROGRAMS scripts/er4ia_motion_check.py scripts/fanuc_controller_emulator.py scripts/fanuc_connection_check.py DESTINATION lib/${PROJECT_NAME})

install(FILES .setup_assistant DESTINATION share/${PROJECT_NAME})

ament_package()
