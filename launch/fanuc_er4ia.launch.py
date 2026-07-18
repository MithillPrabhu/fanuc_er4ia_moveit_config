from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import (
    generate_move_group_launch,
    generate_moveit_rviz_launch,
    generate_rsp_launch,
)


def generate_launch_description():
    robot_model = "er4ia"
    robot_series = "lrmate"

    use_mock = LaunchConfiguration("use_mock")
    robot_ip = LaunchConfiguration("robot_ip")

    package_path = Path(get_package_share_directory("fanuc_er4ia_moveit_config"))
    hardware_interface_path = Path(get_package_share_directory("fanuc_hardware_interface"))

    declared_arguments = [
        DeclareLaunchArgument(
            "use_mock",
            default_value="true",
            description="Use mock hardware instead of a physical or ROBOGUIDE controller.",
        ),
        DeclareLaunchArgument(
            "robot_ip",
            default_value="192.168.1.48",
            description="IP address of the physical or ROBOGUIDE virtual controller.",
        ),
    ]

    moveit_config = (
        MoveItConfigsBuilder(robot_model, package_name="fanuc_er4ia_moveit_config")
        .robot_description(
            file_path=str(hardware_interface_path / "robot" / "6dof_robot.urdf.xacro"),
            mappings={
                "robot_model": robot_model,
                "robot_series": robot_series,
                "use_mock": use_mock,
                "robot_ip": robot_ip,
            },
        )
        .robot_description_semantic(file_path="config/er4ia.srdf")
        .robot_description_kinematics(file_path="config/kinematics.yaml")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_scene_monitor(
            publish_robot_description=True,
            publish_robot_description_semantic=True,
        )
        .planning_pipelines(pipelines=["ompl"])
        .to_moveit_configs()
    )

    ros2_control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[str(package_path / "config" / "ros2_controllers.yaml")],
        remappings=[("~/robot_description", "/robot_description")],
        output="screen",
    )

    spawn_controllers = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(package_path / "launch" / "spawn_controllers.launch.py"))
    )

    return LaunchDescription(
        declared_arguments
        + [
            generate_rsp_launch(moveit_config),
            ros2_control_node,
            generate_move_group_launch(moveit_config),
            generate_moveit_rviz_launch(moveit_config),
            spawn_controllers,
        ]
    )
