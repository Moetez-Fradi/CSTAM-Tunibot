import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    package_share = get_package_share_directory("cstam_robot")
    world = os.path.join(package_share, "worlds", "test_world.sdf")
    model = PathJoinSubstitution([
        FindPackageShare("cstam_robot"), "urdf", "cstam_robot.urdf.xacro"
    ])
    robot_description = {
        "robot_description": ParameterValue(
            Command(["xacro ", model]), value_type=str
        )
    }

    gz_source = PythonLaunchDescriptionSource([
        PathJoinSubstitution([
            FindPackageShare("ros_gz_sim"), "launch", "gz_sim.launch.py"
        ])
    ])
    gz_gui = IncludeLaunchDescription(
        gz_source,
        condition=UnlessCondition(LaunchConfiguration("headless")),
        launch_arguments={"gz_args": f"-r {world}"}.items(),
    )
    gz_server = IncludeLaunchDescription(
        gz_source,
        condition=IfCondition(LaunchConfiguration("headless")),
        launch_arguments={"gz_args": f"-r --headless-rendering {world}"}.items(),
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
            "/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V",
            "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan",
            "/camera/rgbd/image@sensor_msgs/msg/Image[gz.msgs.Image",
            "/camera/rgbd/depth_image@sensor_msgs/msg/Image[gz.msgs.Image",
            "/camera/rgbd/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo",
        ],
        output="screen",
    )

    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=[
            "-name", "cstam_service_robot",
            "-topic", "robot_description",
            "-x", "0",
            "-y", "0",
            "-z", "0.02",
        ],
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", PathJoinSubstitution([
            FindPackageShare("cstam_robot"), "rviz", "cstam_robot.rviz"
        ])],
        condition=IfCondition(LaunchConfiguration("rviz")),
        output="screen",
    )

    return LaunchDescription([
        DeclareLaunchArgument("headless", default_value="false"),
        DeclareLaunchArgument("rviz", default_value="false"),
        gz_gui,
        gz_server,
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[robot_description],
            output="screen",
        ),
        bridge,
        TimerAction(period=3.0, actions=[spawn]),
        rviz,
    ])
