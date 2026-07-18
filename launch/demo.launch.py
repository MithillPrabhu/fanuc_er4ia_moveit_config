from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import (
    generate_move_group_launch,
    generate_moveit_rviz_launch,
    generate_rsp_launch,
    generate_spawn_controllers_launch,
)


def generate_launch_description():
    package_path = Path(get_package_share_directory("fanuc_er4ia_moveit_config"))

    moveit_config = (
        MoveItConfigsBuilder("er4ia", package_name="fanuc_er4ia_moveit_config")
        .robot_description(file_path="config/er4ia.urdf.xacro")
        .robot_description_semantic(file_path="config/er4ia.srdf")
        .robot_description_kinematics(file_path="config/kinematics.yaml")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_scene_monitor(
            publish_robot_description=True,
            publish_robot_description_semantic=True,
        )
        .planning_pipelines(pipelines=["ompl", "pilz_industrial_motion_planner"])
        .to_moveit_configs()
    )

    ros2_control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[str(package_path / "config" / "ros2_controllers.yaml")],
        remappings=[("~/robot_description", "/robot_description")],
        output="screen",
    )

    return LaunchDescription(
        [
            generate_rsp_launch(moveit_config),
            ros2_control_node,
            generate_move_group_launch(moveit_config),
            generate_moveit_rviz_launch(moveit_config),
            generate_spawn_controllers_launch(moveit_config),
        ]
    )
