# Bring up the FANUC ER-4iA with MoveIt 2 on top of the official FANUC ROS 2
# driver (fanuc_hardware_interface). Works with mock hardware, a ROBOGUIDE
# virtual controller, or a real R-30iB Plus / R-30iB Mate Plus / R-50iA.
#
# Adapted from fanuc_moveit_config/launch/fanuc_moveit_template.launch.py
# (Copyright 2025 FANUC America Corporation / FANUC CORPORATION, Apache-2.0).
#
# Examples:
#   # mock hardware (no controller needed)
#   ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py
#   # ROBOGUIDE on a Windows PC at 192.168.1.48 on the same network
#   ros2 launch fanuc_er4ia_moveit_config fanuc_er4ia.launch.py \
#       use_mock:=false robot_ip:=192.168.1.48

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from moveit_configs_utils import MoveItConfigsBuilder
from ament_index_python.packages import get_package_share_directory
import os

ROBOT_MODEL = "er4ia"
ROBOT_SERIES = "lrmate"  # -> fanuc_lrmate_description
PACKAGE = "fanuc_er4ia_moveit_config"


def launch_setup(context, *args, **kwargs):
    robot_ip = LaunchConfiguration("robot_ip")
    ros2_control_config = LaunchConfiguration("ros2_control_config")
    gpio_config_package = LaunchConfiguration("gpio_config_package")
    gpio_config_path = LaunchConfiguration("gpio_config_path")
    use_mock = LaunchConfiguration("use_mock")
    motion_control = LaunchConfiguration("motion_control")
    initial_controller = LaunchConfiguration("initial_controller")
    encoding = LaunchConfiguration("encoding")
    launch_rviz = LaunchConfiguration("launch_rviz")

    common_control_args = {
        "robot_model": ROBOT_MODEL,
        "robot_series": ROBOT_SERIES,
        "gpio_config_package": gpio_config_package,
        "gpio_config_path": gpio_config_path,
        "ros2_control_config": ros2_control_config,
        "launch_rviz": "false",
    }

    # ros2_control_node + robot_state_publisher + controller spawners,
    # provided by FANUC's driver.
    physical_control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("fanuc_hardware_interface"),
                    "launch",
                    "fanuc_physical_control.launch.py",
                ]
            )
        ),
        launch_arguments={
            **common_control_args,
            "robot_ip": robot_ip,
            "use_mock": use_mock,
            "motion_control": motion_control,
            "initial_controller": initial_controller,
            "encoding": encoding,
        }.items(),
        condition=UnlessCondition(use_mock),
    )

    mock_control = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("fanuc_hardware_interface"),
                    "launch",
                    "fanuc_mock_control.launch.py",
                ]
            )
        ),
        launch_arguments=common_control_args.items(),
        condition=IfCondition(use_mock),
    )

    description_mappings = {
        "robot_ip": robot_ip.perform(context),
        "robot_model": ROBOT_MODEL,
        "robot_series": ROBOT_SERIES,
        "use_mock": use_mock.perform(context),
        "gpio_configuration": PathJoinSubstitution(
            [FindPackageShare(gpio_config_package), gpio_config_path]
        ),
        "motion_control": motion_control.perform(context),
        "encoding": encoding.perform(context),
    }

    urdf_path = os.path.join(
        get_package_share_directory("fanuc_hardware_interface"),
        "robot",
        "6dof_robot.urdf.xacro",
    )

    moveit_config = (
        MoveItConfigsBuilder(ROBOT_MODEL, package_name=PACKAGE)
        .robot_description(file_path=urdf_path, mappings=description_mappings)
        .robot_description_semantic(file_path="config/er4ia.srdf")
        .robot_description_kinematics(file_path="config/kinematics.yaml")
        .joint_limits(file_path="config/joint_limits.yaml")
        # FANUC driver controllers (ScaledJointTrajectoryController) are
        # discovered through ros2_control, not the simple controller manager.
        .trajectory_execution(file_path="config/fanuc_moveit_controllers.yaml")
        .planning_scene_monitor(
            publish_robot_description=True,
            publish_robot_description_semantic=True,
        )
        .planning_pipelines(pipelines=["ompl"])
        .to_moveit_configs()
    )

    move_group = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="log",
        parameters=[moveit_config.to_dict()],
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="log",
        arguments=[
            "--display-config",
            PathJoinSubstitution([FindPackageShare(PACKAGE), "config", "moveit.rviz"]),
        ],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.planning_pipelines,
            moveit_config.robot_description_kinematics,
            moveit_config.joint_limits,
        ],
        condition=IfCondition(launch_rviz),
    )

    return [physical_control, mock_control, move_group, rviz]


def generate_launch_description():
    declared_arguments = [
        DeclareLaunchArgument(
            "use_mock",
            default_value="true",
            description="true: mock hardware. false: ROBOGUIDE or a real controller.",
        ),
        DeclareLaunchArgument(
            "robot_ip",
            default_value="192.168.1.48",
            description="IP of the real controller, or of the Windows PC running ROBOGUIDE.",
        ),
        DeclareLaunchArgument(
            "ros2_control_config",
            default_value=PathJoinSubstitution(
                [
                    FindPackageShare("fanuc_hardware_interface"),
                    "config",
                    "example_ros2_controllers.yaml",
                ]
            ),
            description="ros2_control controllers file (FANUC defaults).",
        ),
        DeclareLaunchArgument(
            "gpio_config_package",
            default_value="fanuc_hardware_interface",
            description="Package that contains the GPIO configuration file.",
        ),
        DeclareLaunchArgument(
            "gpio_config_path",
            default_value="config/example_gpio_config_small.yaml",
            description="GPIO configuration file inside gpio_config_package.",
        ),
        DeclareLaunchArgument(
            "motion_control",
            default_value="1",
            description="Initial motion control state.",
        ),
        DeclareLaunchArgument(
            "initial_controller",
            default_value="joint_trajectory_controller",
            choices=["joint_trajectory_controller", "fanuc_rmi_controller", "none"],
            description="Controller activated at start-up.",
        ),
        DeclareLaunchArgument(
            "encoding",
            default_value="UTF-8",
            description="Controller text encoding (SHIFT-JIS for a Japanese R-30iB Plus).",
        ),
        DeclareLaunchArgument(
            "launch_rviz",
            default_value="true",
            description="Start RViz with the MoveIt MotionPlanning panel.",
        ),
    ]
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
