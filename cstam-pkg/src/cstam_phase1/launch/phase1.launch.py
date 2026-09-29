"""One-command first-floor CSTAM simulation, localization and delivery bringup."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    phase1_share = get_package_share_directory('cstam_phase1')
    restaurant_share = get_package_share_directory('andino_gz')
    slam = LaunchConfiguration('slam')
    rviz = LaunchConfiguration('rviz')
    slam_condition = IfCondition(
        PythonExpression(["'", slam, "'.lower() == 'true'"]))
    normal_condition = IfCondition(
        PythonExpression(["'", slam, "'.lower() != 'true'"]))
    rviz_condition = IfCondition(
        PythonExpression(["'", rviz, "'.lower() == 'true'"]))

    robot_x = LaunchConfiguration('robot_x')
    robot_y = LaunchConfiguration('robot_y')
    robot_z = LaunchConfiguration('robot_z')
    robot_yaw = LaunchConfiguration('robot_yaw')
    initial_x = LaunchConfiguration('initial_pose_x')
    initial_y = LaunchConfiguration('initial_pose_y')
    initial_yaw = LaunchConfiguration('initial_pose_yaw')

    restaurant = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(restaurant_share, 'launch', 'restaurant.launch.py')),
        launch_arguments={
            'robot_x': robot_x,
            'robot_y': robot_y,
            'robot_z': robot_z,
            'robot_yaw': robot_yaw,
            'headless': LaunchConfiguration('headless'),
            'autostart': 'True',
            'rviz': 'False',
            'use_webcam': 'False',
            'start_app': 'False',
        }.items(),
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            phase1_share, 'launch', 'nav2_phase1.launch.py')),
        launch_arguments={
            'map': PathJoinSubstitution([
                FindPackageShare('cstam_phase1'), 'maps', 'restaurant',
                'restaurant.yaml']),
            'params_file': PathJoinSubstitution([
                FindPackageShare('cstam_phase1'), 'config', 'nav2_params.yaml']),
        }.items(),
        condition=normal_condition,
    )

    initial_pose = Node(
        package='cstam_phase1',
        executable='initial_pose_publisher',
        name='cstam_initial_pose_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'x': initial_x,
            'y': initial_y,
            'yaw': initial_yaw,
        }],
        condition=normal_condition,
    )

    task_manager = Node(
        package='cstam_phase1',
        executable='delivery_task_manager',
        name='cstam_delivery_task_manager',
        output='screen',
        parameters=[{'use_sim_time': True}],
        condition=normal_condition,
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            phase1_share, 'launch', 'cstam_slam.launch.py')),
        condition=slam_condition,
    )

    pointcloud_filter = Node(
        package='cstam_phase1',
        executable='pointcloud_navigation_filter',
        name='cstam_pointcloud_navigation_filter',
        output='screen',
        parameters=[{'use_sim_time': True}],
    )

    drive_reference_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='cstam_drive_reference_tf',
        arguments=['0.18', '0', '0', '0', '0', '0',
                   'base_drive', 'base_footprint'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='cstam_phase1_rviz',
        arguments=['-d', os.path.join(phase1_share, 'rviz', 'cstam_phase1.rviz')],
        parameters=[{'use_sim_time': True}],
        output='screen',
        condition=rviz_condition,
    )

    return LaunchDescription([
        # Fast DDS shared-memory locks can survive an interrupted ROS process
        # and have caused dropped lifecycle responses on this workstation.
        # Keep Phase 1 transport project-scoped and deterministic over UDP.
        SetEnvironmentVariable(
            'FASTDDS_DEFAULT_PROFILES_FILE',
            os.path.join(phase1_share, 'config', 'fastdds_udp.xml')),
        SetEnvironmentVariable(
            'FASTRTPS_DEFAULT_PROFILES_FILE',
            os.path.join(phase1_share, 'config', 'fastdds_udp.xml')),
        DeclareLaunchArgument('slam', default_value='false',
                              description='Run SLAM mapping instead of AMCL/Nav2.'),
        DeclareLaunchArgument('rviz', default_value='false',
                              description='Open the CSTAM Phase 1 RViz view.'),
        DeclareLaunchArgument('headless', default_value='false',
                              description='Run Gazebo without its GUI.'),
        # The upper rectangle is the actual first-floor restaurant area; the
        # lower rectangle is an empty approach area separated by a solid wall.
        DeclareLaunchArgument('robot_x', default_value='11.4'),
        DeclareLaunchArgument('robot_y', default_value='6.95'),
        DeclareLaunchArgument('robot_z', default_value='0.02'),
        DeclareLaunchArgument('robot_yaw', default_value='0.0'),
        DeclareLaunchArgument('initial_pose_x', default_value='-3.63'),
        DeclareLaunchArgument('initial_pose_y', default_value='1.08'),
        DeclareLaunchArgument('initial_pose_yaw', default_value='-0.522'),
        restaurant,
        drive_reference_tf,
        pointcloud_filter,
        slam_launch,
        nav2,
        initial_pose,
        task_manager,
        rviz_node,
    ])
