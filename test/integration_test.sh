#!/usr/bin/env bash
# End-to-end test: MoveIt -> FANUC ROS 2 driver -> (emulated) controller.
#
#   test/integration_test.sh mock       # mock hardware only
#   test/integration_test.sh emulator   # real fanuc_hardware_interface over UDP/TCP
#                                       # against scripts/fanuc_controller_emulator.py
#
# Run from a sourced workspace (source install/setup.bash).
set -u
MODE="${1:-emulator}"
IP="${ROBOT_IP:-127.0.0.1}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/roslog}"
LOG_DIR="${LOG_DIR:-/tmp/er4ia_test}"
mkdir -p "$LOG_DIR"
PIDS=()

cleanup() {
  for p in "${PIDS[@]}"; do kill -INT "$p" 2>/dev/null; done
  sleep 3
  pkill -f "move_group|ros2_control_node|robot_state_publisher|controller_manager/spawner|slider_gui_node|fanuc_controller_emulator" 2>/dev/null
  true
}
trap cleanup EXIT

if [ "$MODE" = "emulator" ]; then
  ros2 run fanuc_er4ia_moveit_config fanuc_controller_emulator.py >"$LOG_DIR/emulator.log" 2>&1 &
  PIDS+=($!)
  sleep 1
  ros2 run fanuc_er4ia_moveit_config fanuc_connection_check.py "$IP" || exit 1
  LAUNCH_ARGS=(use_mock:=false "robot_ip:=$IP")
else
  LAUNCH_ARGS=(use_mock:=true)
fi

ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py launch_rviz:=false "${LAUNCH_ARGS[@]}" \
  >"$LOG_DIR/launch_$MODE.log" 2>&1 &
PIDS+=($!)

# Wait for the trajectory controller to come up.
for _ in $(seq 1 60); do
  if ros2 control list_controllers 2>/dev/null | grep -q "joint_trajectory_controller.*active"; then
    break
  fi
  sleep 2
done
ros2 control list_controllers 2>/dev/null

timeout 180 ros2 run fanuc_er4ia_moveit_config er4ia_motion_check.py
RESULT=$?
echo "integration test ($MODE): $([ $RESULT -eq 0 ] && echo PASS || echo FAIL)"
if [ $RESULT -ne 0 ]; then
  echo "---- launch log (tail)"; tail -n 60 "$LOG_DIR/launch_$MODE.log"
fi
exit $RESULT
