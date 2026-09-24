from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
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
    rviz_config = PathJoinSubstitution([
        FindPackageShare("cstam_robot"), "rviz", "cstam_robot.rviz"
    ])

    return LaunchDescription([
        DeclareLaunchArgument("use_gui", default_value="false"),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[robot_description],
            output="screen",
        ),
        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            condition=IfCondition(LaunchConfiguration("use_gui")),
            output="screen",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            arguments=["-d", rviz_config],
            output="screen",
        ),
    ])
