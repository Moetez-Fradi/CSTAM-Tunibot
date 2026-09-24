"""Spawn the standalone CSTAM robot into an already-running Gazebo world."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    model = PathJoinSubstitution([
        FindPackageShare("cstam_robot"), "urdf", "cstam_robot.urdf.xacro"
    ])
    robot_description = {
        "robot_description": ParameterValue(
            Command(["xacro ", model]), value_type=str
        )
    }

    entity = LaunchConfiguration("entity")
    initial_pose_x = LaunchConfiguration("initial_pose_x")
    initial_pose_y = LaunchConfiguration("initial_pose_y")
    initial_pose_z = LaunchConfiguration("initial_pose_z")
    initial_pose_yaw = LaunchConfiguration("initial_pose_yaw")
    robot_description_topic = LaunchConfiguration("robot_description_topic")
    use_sim_time = LaunchConfiguration("use_sim_time")

    return LaunchDescription([
        DeclareLaunchArgument("entity", default_value="cstam"),
        DeclareLaunchArgument("initial_pose_x", default_value="0.0"),
        DeclareLaunchArgument("initial_pose_y", default_value="0.0"),
        DeclareLaunchArgument("initial_pose_z", default_value="0.02"),
        DeclareLaunchArgument("initial_pose_yaw", default_value="0.0"),
        DeclareLaunchArgument(
            "robot_description_topic", default_value="robot_description"
        ),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="both",
            parameters=[robot_description, {"use_sim_time": use_sim_time}],
            remappings=[("/tf", "tf"), ("/tf_static", "tf_static")],
        ),
        Node(
            package="ros_gz_sim",
            executable="create",
            arguments=[
                "-name", entity,
                "-topic", robot_description_topic,
                "-x", initial_pose_x,
                "-y", initial_pose_y,
                "-z", initial_pose_z,
                "-R", "0",
                "-P", "0",
                "-Y", initial_pose_yaw,
            ],
            output="screen",
        ),
    ])
