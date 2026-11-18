#!/usr/bin/env python3
"""Smoke test: ask MoveIt to plan and execute a few joint goals on the ER-4iA.

Works with mock hardware, a ROBOGUIDE virtual controller, or a real robot.
Start fanuc_er4ia.launch.py first, then:

    ros2 run fanuc_er4ia_moveit_config er4ia_motion_check.py
    ros2 run fanuc_er4ia_moveit_config er4ia_motion_check.py --ros-args -p velocity_scaling:=0.05

Exit code 0 means every goal was planned, executed and reached.
"""

import math
import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, MoveItErrorCodes
from sensor_msgs.msg import JointState

JOINTS = ["J1", "J2", "J3", "J4", "J5", "J6"]

# Small, safe poses (degrees) well inside the ER-4iA joint limits.
WAYPOINTS_DEG = [
    [0, 0, 0, 0, -90, 0],
    [30, 10, -10, 0, -60, 45],
    [-30, 15, 5, 20, -90, -45],
    [0, 0, 0, 0, -90, 0],
]


class MotionCheck(Node):
    def __init__(self):
        super().__init__("er4ia_motion_check")
        self.declare_parameter("group", "arm")
        self.declare_parameter("velocity_scaling", 0.2)
        self.declare_parameter("acceleration_scaling", 0.2)
        self.declare_parameter("tolerance_deg", 1.0)
        self.client = ActionClient(self, MoveGroup, "move_action")
        self.joint_state = None
        self.create_subscription(JointState, "joint_states", self._on_js, 10)

    def _on_js(self, msg):
        self.joint_state = dict(zip(msg.name, msg.position))

    def wait_ready(self, timeout=120.0):
        end = time.time() + timeout
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.2)
            if self.joint_state and self.client.server_is_ready():
                return True
        return False

    def move_to(self, target_deg):
        target = [math.radians(v) for v in target_deg]
        goal = MoveGroup.Goal()
        req = goal.request
        req.group_name = self.get_parameter("group").value
        req.num_planning_attempts = 5
        req.allowed_planning_time = 5.0
        req.max_velocity_scaling_factor = self.get_parameter("velocity_scaling").value
        req.max_acceleration_scaling_factor = self.get_parameter("acceleration_scaling").value
        c = Constraints()
        for name, pos in zip(JOINTS, target):
            jc = JointConstraint(joint_name=name, position=pos,
                                 tolerance_above=0.001, tolerance_below=0.001, weight=1.0)
            c.joint_constraints.append(jc)
        req.goal_constraints.append(c)
        goal.planning_options.plan_only = False

        send = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send)
        handle = send.result()
        if not handle or not handle.accepted:
            self.get_logger().error("MoveGroup goal rejected")
            return False
        res_f = handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_f)
        code = res_f.result().result.error_code.val
        if code != MoveItErrorCodes.SUCCESS:
            self.get_logger().error(f"MoveIt error code {code}")
            return False

        # Let joint_states settle, then compare with the target.
        end = time.time() + 2.0
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.1)
        tol = math.radians(self.get_parameter("tolerance_deg").value)
        err = max(abs(self.joint_state[j] - t) for j, t in zip(JOINTS, target))
        ok = err <= tol
        self.get_logger().info(
            f"target {target_deg} deg -> max error {math.degrees(err):.3f} deg "
            f"{'OK' if ok else 'FAIL'}"
        )
        return ok


def main():
    rclpy.init()
    node = MotionCheck()
    if not node.wait_ready():
        node.get_logger().error("No /joint_states or move_action server. Is the launch running?")
        sys.exit(2)
    results = [node.move_to(wp) for wp in WAYPOINTS_DEG]
    passed = all(results)
    node.get_logger().info(f"{sum(results)}/{len(results)} goals reached -> "
                           f"{'PASS' if passed else 'FAIL'}")
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
