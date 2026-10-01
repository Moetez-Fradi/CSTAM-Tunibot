"""One-command first-floor CSTAM simulation, localization and delivery bringup."""

import os
import math

import yaml

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
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
    with open(os.path.join(phase1_share, 'maps', 'restaurant', 'locations.yaml'),
              encoding='utf-8') as stream:
        dock = yaml.safe_load(stream)['dock']
    with open(os.path.join(phase1_share, 'maps', 'restaurant', 'world_alignment.yaml'),
              encoding='utf-8') as stream:
        alignment = yaml.safe_load(stream)['world_from_map']
    angle = alignment['yaw']
    dock_world_x = alignment['x'] + math.cos(angle) * dock['x'] - math.sin(angle) * dock['y']
    dock_world_y = alignment['y'] + math.sin(angle) * dock['x'] + math.cos(angle) * dock['y']
    dock_world_yaw = angle + dock['yaw']
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
            'params_file': LaunchConfiguration('nav2_params_file'),
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
        # DiffDrive integrates wheel angles at a virtual skid-steer centre;
        # selecting front encoders does not place its frame at the front axle.
        # Real repeated-turn comparison: the former 0.18 m lever produced
        # AMCL translation drift up to 0.97 m; a centred reference stayed
        # within 0.18 m. Both frames are ground projections of the body centre.
        arguments=['0', '0', '0', '0', '0', '0',
                   'base_drive', 'base_footprint'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='cstam_phase1_rviz',
        arguments=['-d', PythonExpression([
            "'", os.path.join(phase1_share, 'rviz', 'cstam_mapping.rviz'),
            "' if '", slam, "'.lower() == 'true' else '",
            os.path.join(phase1_share, 'rviz', 'cstam_phase1.rviz'), "'"])],
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
        DeclareLaunchArgument(
            'nav2_params_file',
            default_value=os.path.join(phase1_share, 'config', 'nav2_params.yaml'),
            description='Nav2 configuration; override only for controlled comparisons.'),
        DeclareLaunchArgument('headless', default_value='False',
                              description='Run Gazebo without its GUI.'),
        # The upper rectangle is the actual first-floor restaurant area; the
        # lower rectangle is an empty approach area separated by a solid wall.
        # Mapping keeps the measured demonstration start. Normal mode spawns
        # at the actual world location corresponding to the semantic dock.
        # AMCL still estimates pose from real scans and wheel odometry.
        DeclareLaunchArgument('robot_x', default_value=PythonExpression([
            "'11.4' if '", slam, "'.lower() == 'true' else '", str(dock_world_x), "'"])),
        DeclareLaunchArgument('robot_y', default_value=PythonExpression([
            "'6.95' if '", slam, "'.lower() == 'true' else '", str(dock_world_y), "'"])),
        DeclareLaunchArgument('robot_z', default_value='0.02'),
        DeclareLaunchArgument('robot_yaw', default_value=PythonExpression([
            "'0.0' if '", slam, "'.lower() == 'true' else '", str(dock_world_yaw), "'"])),
        DeclareLaunchArgument('initial_pose_x', default_value=str(dock['x'])),
        DeclareLaunchArgument('initial_pose_y', default_value=str(dock['y'])),
        DeclareLaunchArgument('initial_pose_yaw', default_value=str(dock['yaw'])),
        # Nested restaurant arguments (notably rviz:=False) must stay local;
        # otherwise they overwrite this launch's RViz setting.
        GroupAction(actions=[restaurant], scoped=True),
        drive_reference_tf,
        pointcloud_filter,
        slam_launch,
        nav2,
        initial_pose,
        task_manager,
        rviz_node,
    ])
