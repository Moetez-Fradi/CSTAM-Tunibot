from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, ExecuteProcess
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
import os
def generate_launch_description():
    rosbridge_port = LaunchConfiguration('rosbridge_port', default='9090')
    web_video_port = LaunchConfiguration('web_video_port', default='8080')
    start_slam     = LaunchConfiguration('start_slam', default='false')
    start_map_http = LaunchConfiguration('start_map_http', default='false')
    map_http_port  = LaunchConfiguration('map_http_port', default='8070')
    camera_topic   = LaunchConfiguration('camera_topic', default='/camera/image_raw/compressed')
    pkg_share_deliverybot = FindPackageShare('deliverybot_bringup')
    rosbridge_ssl = LaunchConfiguration('rosbridge_ssl', default='true')
    rosbridge_certfile = LaunchConfiguration(
        'rosbridge_certfile',
        default=PathJoinSubstitution([
            pkg_share_deliverybot, 'certs', 'cert.pem'
        ])
    )
    rosbridge_keyfile = LaunchConfiguration(
        'rosbridge_keyfile',
        default=PathJoinSubstitution([
            pkg_share_deliverybot, 'certs', 'key.pem'
        ])
    )
    pkg_share_map_info = get_package_share_directory('map_info')
    default_yaml = os.path.expanduser('~/ws/src/App/map_info/maps/office_simulation.yaml')
    yaml_path           = LaunchConfiguration('yaml_path', default=default_yaml)
    frame_id            = LaunchConfiguration('frame_id', default='map')
    topic_goal_name     = LaunchConfiguration('topic_goal_name', default='/app/goal_name')
    topic_goal_cancel = LaunchConfiguration('topic_goal_cancel', default='/app/goal_cancel')
    topic_status      = LaunchConfiguration('topic_status', default='/app/goal_status')
    server_timeout    = LaunchConfiguration('server_timeout', default='8.0')
    fuzzy_cutoff      = LaunchConfiguration('fuzzy_cutoff', default='0.7')
    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{
            'port': rosbridge_port,
            'ssl': rosbridge_ssl,
            'certfile': rosbridge_certfile,
            'keyfile': rosbridge_keyfile,
        }],
        output='screen'
    )
    web_video = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        parameters=[{
            'port': web_video_port,
            'address': '0.0.0.0',
            'default_transport': 'compressed'
        }],
        output='screen'
    )
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                os.environ.get('AMENT_PREFIX_PATH', '').split(':')[0],
                'share', 'slam_toolbox', 'launch', 'online_async_launch.py'
            )
        ),
        condition=IfCondition(start_slam)
    )
    map_http = Node(
        package='map_http_bridge',
        executable='map_http_bridge',
        name='map_http_bridge',
        parameters=[{'port': map_http_port, 'topic': '/map'}],
        condition=IfCondition(start_map_http),
        output='screen'
    )
    app_goal_gateway = Node(
        package='map_info',              
        executable='app_goal_gateway',    
        name='app_goal_gateway',
        parameters=[{
            'yaml_path': yaml_path,
            'frame_id': frame_id,
            'topic_goal_name': topic_goal_name,
            'topic_goal_cancel': topic_goal_cancel,
            'topic_status': topic_status,
            'server_timeout': server_timeout,
            'fuzzy_cutoff': fuzzy_cutoff,
        }],
        output='screen'
    )
    qr_generator = Node(
        package='qr_verification',
        executable='qr_generator',
        name='qr_generator'
    )
    qr_scanner = Node(
        package='qr_verification',
        executable='qr_scanner',
        name='qr_scanner'
    )
    like_detector = Node(
        package='yolo_like_detector',
        executable='like_detector_node',
        name='like_detector_node',
        output='screen'
    )
    chat_bridge = Node(
        package='deliverybot_bringup',
        executable='chat_bridge.py',
        output='screen'
    )
    order_logger = Node(
        package='order_logger',
        executable='order_logger_node',
        name='order_logger_node',
        output='screen'
    )
    return LaunchDescription([
        DeclareLaunchArgument('rosbridge_port', default_value='9090'),
        DeclareLaunchArgument('web_video_port', default_value='8080'),
        DeclareLaunchArgument('start_slam', default_value='false'),
        DeclareLaunchArgument('start_map_http', default_value='false'),
        DeclareLaunchArgument('map_http_port', default_value='8070'),
        DeclareLaunchArgument('camera_topic', default_value='/camera/image_raw/compressed'),
        DeclareLaunchArgument('rosbridge_ssl', default_value='true'),
        DeclareLaunchArgument(
            'rosbridge_certfile',
            default_value=PathJoinSubstitution([
                pkg_share_deliverybot, 'certs', 'cert.pem'
            ])
        ),
        DeclareLaunchArgument(
            'rosbridge_keyfile',
            default_value=PathJoinSubstitution([
                pkg_share_deliverybot, 'certs', 'key.pem'
            ])
        ),
        DeclareLaunchArgument('yaml_path', default_value=default_yaml),
        DeclareLaunchArgument('frame_id', default_value='map'),
        DeclareLaunchArgument('topic_goal_name', default_value='/app/goal_name'),
        DeclareLaunchArgument('topic_goal_cancel', default_value='/app/goal_cancel'),
        DeclareLaunchArgument('topic_status', default_value='/app/goal_status'),
        DeclareLaunchArgument('server_timeout', default_value='8.0'),
        DeclareLaunchArgument('fuzzy_cutoff', default_value='0.7'),
        rosbridge,
        web_video,
        slam,
        map_http,
        app_goal_gateway,
        qr_generator,
        qr_scanner,
        like_detector,
        chat_bridge,
        order_logger,
        ExecuteProcess(
            cmd=[
                'python3', '-m', 'streamlit', 'run', 
                os.path.join(os.environ['HOME'], 'ws/src/App/order_logger/dashboard/dashboard.py'),
                '--server.port', '8501',
                '--server.headless', 'false'
            ],
            cwd=os.path.join(os.environ['HOME'], 'ws/src/App/order_logger/dashboard'),
            output='screen'
        )
    ])
