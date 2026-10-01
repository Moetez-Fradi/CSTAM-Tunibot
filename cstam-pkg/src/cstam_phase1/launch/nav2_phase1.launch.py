"""Explicit, non-composed Nav2 launch for the CSTAM first-floor MVP."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    map_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    common = [params_file, {'use_sim_time': True}]
    tf_remappings = [('/tf', 'tf'), ('/tf_static', 'tf_static')]

    localization_nodes = ['map_server', 'amcl']
    navigation_nodes = [
        'controller_server', 'smoother_server', 'planner_server',
        'behavior_server', 'bt_navigator', 'waypoint_follower',
        'velocity_smoother',
    ]
    nodes = [
        Node(
            package='nav2_map_server', executable='map_server', name='map_server',
            output='screen', parameters=common + [{'yaml_filename': map_file}],
            remappings=tf_remappings),
        Node(
            package='nav2_amcl', executable='amcl', name='amcl', output='screen',
            parameters=common, remappings=tf_remappings),
        Node(
            package='nav2_lifecycle_manager', executable='lifecycle_manager',
            name='lifecycle_manager_localization', output='screen',
            parameters=[{
                'use_sim_time': True,
                'autostart': True,
                'node_names': localization_nodes,
                'bond_timeout': 4.0,
            }]),
    ]
    package_by_executable = {
        'controller_server': 'nav2_controller',
        'smoother_server': 'nav2_smoother',
        'planner_server': 'nav2_planner',
        'behavior_server': 'nav2_behaviors',
        'bt_navigator': 'nav2_bt_navigator',
        'waypoint_follower': 'nav2_waypoint_follower',
        'velocity_smoother': 'nav2_velocity_smoother',
    }
    for executable in navigation_nodes:
        remappings = list(tf_remappings)
        if executable in ('controller_server', 'behavior_server'):
            remappings.append(('cmd_vel', 'cmd_vel_nav'))
        elif executable == 'velocity_smoother':
            # One smoothed command stream reaches Gazebo. Previously the
            # smoother output had zero subscribers and was bypassed.
            remappings.extend([
                ('cmd_vel', 'cmd_vel_nav'),
                ('cmd_vel_smoothed', 'cmd_vel'),
            ])
        nodes.append(Node(
            package=package_by_executable[executable],
            executable=executable,
            name=executable,
            output='screen',
            parameters=common,
            remappings=remappings))
    nodes.append(Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen',
        parameters=[{
            'use_sim_time': True,
            'autostart': True,
            'node_names': navigation_nodes,
            'bond_timeout': 4.0,
        }]))

    return LaunchDescription([
        DeclareLaunchArgument('map'),
        DeclareLaunchArgument('params_file'),
        *nodes,
    ])
