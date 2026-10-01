
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression, TextSubstitution
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from launch_ros.substitutions import FindPackageShare
from andino_gz.launch_tools.substitutions import TextJoin


def _parse_multi_robot_pose(robots_text):
    """Parse the repository's ``name={x: ..., y: ..., z: ..., yaw: ...};`` syntax."""
    import yaml

    robots = {}
    for item in robots_text.split(';'):
        item = item.strip()
        if not item:
            continue
        name, pose_text = item.split('=', 1)
        pose = yaml.safe_load(pose_text.strip())
        robots[name.strip()] = {
            key: float(value) for key, value in pose.items()
        }
    return robots


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_cstam_robot = get_package_share_directory('cstam_robot')
    try:
        pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    except Exception:
        # Nav2 is optional for the simulation bring-up.  The include is still
        # guarded by nav2:=True and will report a clear missing-package error
        # only if a user explicitly enables Nav2.
        pkg_nav2_bringup = ''
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS bridge node.')
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='populated_office.sdf', description='Name of the world to load. Match with map if using Nav2.')
    robots_arg = DeclareLaunchArgument(
        'robots', default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn, multiple robots can be stated separated by a ; ')
    robot_type_arg = DeclareLaunchArgument(
        'robot_type', default_value='andino', choices=['andino', 'cstam'],
        description='Robot package/model to spawn in the existing Gazebo world.')
    gui_config_arg = DeclareLaunchArgument(
        'gui_config',
        default_value='default.config',
        description='Name of the gui configuration file to load.')
    nav2_arg = DeclareLaunchArgument(
        'nav2', default_value='False',
        description='Enable Nav2 Bringup.')
    map_name_arg = DeclareLaunchArgument(
      'map', default_value="office", description='Name of the map to load. It should match the world_name.'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 configuration. Full path to the ROS2 parameters file to use for all launched nodes')
    autostart_arg = DeclareLaunchArgument(
        'autostart',
        default_value='False',
        choices=['True', 'False'],
        description='If true, the simulation starts automatically.',
    )
    headless_arg = DeclareLaunchArgument(
        'headless', default_value='False', choices=['True', 'False'],
        description='Run Gazebo server-only for CI or terminal-only sessions.',
    )
    use_webcam_arg = DeclareLaunchArgument(
        'use_webcam',
        default_value='False',
        description='Use laptop webcam for compressed stream (QR/YOLO)',
    )
    start_app_arg = DeclareLaunchArgument(
        'start_app',
        default_value='False',
        description='Start application layer (QR scanner, YOLO detector, etc.)',
    )
    rviz = LaunchConfiguration('rviz')
    ros_bridge = LaunchConfiguration('ros_bridge')
    world_name = LaunchConfiguration('world_name')
    map_name = LaunchConfiguration('map')
    gui_config = LaunchConfiguration('gui_config')
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    nav2_flag = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')
    autostart = LaunchConfiguration('autostart')
    headless = LaunchConfiguration('headless')
    use_webcam = LaunchConfiguration('use_webcam')
    start_app = LaunchConfiguration('start_app')
    robot_type = LaunchConfiguration('robot_type')
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name ,'.yaml'])])
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=["--gui-config ", gui_config_path]),
            PythonExpression(['" -s" if "', headless, '" == "True" else ""']),
            PythonExpression(['" -r" if "', autostart, '" == "True" else ""']),
        ],
        separator=' ',
    )
    base_group = GroupAction(
        scoped=True, forwarding=False,
        launch_configurations={
            'ros_bridge': ros_bridge,
            'world_name': world_name,
            'gui_config': gui_config,
            'autostart': autostart,
            'headless': headless,
            'use_webcam': use_webcam,
        },
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            # Node(
            #     package='ros_gz_bridge',
            #     executable='parameter_bridge',
            #     arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
            #     output='screen',
            #     namespace='andino_gz_sim',
            #     condition=IfCondition(ros_bridge),
            # ),
        ]
    )
    def setup_robots(context):
        robots_text = LaunchConfiguration('robots').perform(context)
        robots_list = _parse_multi_robot_pose(robots_text)
        if robots_list == {}:
            robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
        more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' > 1'])
        one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' == 1'])
        actions = [
            LogInfo(msg="Robots to spawn: " + str(robots_list)),
        ]
        for robot_name, init_pose in robots_list.items():
            robots_group = GroupAction(
                scoped=True, forwarding=False,
                launch_configurations={
                    'rviz': rviz,
                    'ros_bridge': ros_bridge,
                    'nav2': nav2_flag,
                    'use_webcam': use_webcam,
                    'robot_type': robot_type,
                },
                actions=[
                    LogInfo(msg="Group for robot: " + robot_name),
                    PushRosNamespace(
                        condition=IfCondition(more_than_one_robot),
                        namespace=robot_name),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')
                        ),
                        launch_arguments={
                            'entity': robot_name,
                            'initial_pose_x': str(init_pose['x']),
                            'initial_pose_y': str(init_pose['y']),
                            'initial_pose_z': str(init_pose['z']),
                            'initial_pose_yaw': str(init_pose['yaw']),
                            'robot_description_topic': 'robot_description',
                            'use_sim_time': 'true',
                        }.items(),
                        condition=IfCondition(PythonExpression(["'", robot_type, "' == 'andino'"])),
                    ),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(pkg_cstam_robot, 'launch', 'spawn_in_gazebo.launch.py')
                        ),
                        launch_arguments={
                            'entity': robot_name,
                            'initial_pose_x': str(init_pose['x']),
                            'initial_pose_y': str(init_pose['y']),
                            'initial_pose_z': str(init_pose['z']),
                            'initial_pose_yaw': str(init_pose['yaw']),
                            'robot_description_topic': 'robot_description',
                            'use_sim_time': 'true',
                        }.items(),
                        condition=IfCondition(PythonExpression(["'", robot_type, "' == 'cstam'"])),
                    ),
                    Node(
                        condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                        package='rviz2', executable='rviz2',
                        arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                        parameters=[{'use_sim_time': True}],
                        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                    ),
                    Node(
                        condition=IfCondition(PythonExpression([rviz, ' and not ', LaunchConfiguration('nav2')])),
                        package='rviz2', executable='rviz2',
                        arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                        parameters=[{'use_sim_time': True}],
                        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                    ),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                        ),
                        launch_arguments={'entity': robot_name, 'use_webcam': use_webcam}.items(),
                        condition=IfCondition(PythonExpression([
                            ros_bridge, ' and ', "'", robot_type, "' == 'andino'"
                        ])),
                    ),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(pkg_cstam_robot, 'launch', 'bridge_in_gazebo.launch.py')
                        ),
                        condition=IfCondition(PythonExpression([
                            ros_bridge, ' and ', "'", robot_type, "' == 'cstam'"
                        ])),
                    ),
                ]
            )
            nav_group = GroupAction(
                scoped=True, forwarding=False,
                launch_configurations={
                    'rviz': rviz,
                    'ros_bridge': ros_bridge,
                    'map': map_path,
                    'params_file': params_file,
                    'nav2': nav2_flag,
                },
                actions=[
                    SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                    SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                        launch_arguments={
                            'namespace': robot_name,
                            'use_namespace': 'True',
                            'map': LaunchConfiguration('map'),
                            'autostart': 'True',
                            'use_sim_time': 'True',
                            'params_file': LaunchConfiguration('params_file'),
                            'use_robot_state_pub': 'False',
                        }.items(),
                        condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')])),
                    ),
                    SetRemap(src='/global_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                    SetRemap(src='/local_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                        launch_arguments={
                            'map': LaunchConfiguration('map'),
                            'autostart': 'True',
                            'use_sim_time': 'True',
                            'params_file': LaunchConfiguration('params_file'),
                            'use_robot_state_pub': 'False',
                        }.items(),
                        condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                    ),
                ]
            )
            actions.extend([robots_group, nav_group])
        return actions

    robot_setup = OpaqueFunction(function=setup_robots)
    pkg_share_path = get_package_share_directory('andino_gz')
    gz_resource_path = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=[
            os.path.join(pkg_share_path, 'models'), ':',
            os.path.join(pkg_share_path, 'worlds'), ':',
            os.environ.get('GZ_SIM_RESOURCE_PATH', '')
        ]
    )
    ign_resource_path = SetEnvironmentVariable(
        name='IGN_GAZEBO_RESOURCE_PATH',
        value=[
             os.path.join(pkg_share_path, 'models'), ':',
            os.path.join(pkg_share_path, 'worlds'), ':',
            os.environ.get('IGN_GAZEBO_RESOURCE_PATH', '')
        ]
    )
    ld = LaunchDescription()
    ld.add_action(gz_resource_path)
    ld.add_action(ign_resource_path)
    ld.add_action(ros_bridge_arg)
    ld.add_action(rviz_arg)
    ld.add_action(world_name_arg)
    ld.add_action(robots_arg)
    ld.add_action(robot_type_arg)
    ld.add_action(gui_config_arg)
    ld.add_action(nav2_arg)
    ld.add_action(map_name_arg)
    ld.add_action(params_file_arg)
    ld.add_action(use_webcam_arg)
    ld.add_action(start_app_arg)
    ld.add_action(autostart_arg)
    ld.add_action(headless_arg)
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)
    ld.add_action(robot_setup)
    # Include the optional application layer only when requested.  Resolving
    # this package eagerly made every simulation fail if the app stack had not
    # been built, even with start_app:=False.
    app_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('deliverybot_bringup'), 'launch', 'app.launch.py'])
        ),
        condition=IfCondition(
            PythonExpression(["'", start_app, "'.lower() == 'true'"])),
    )
    ld.add_action(app_launch)
    return ld
