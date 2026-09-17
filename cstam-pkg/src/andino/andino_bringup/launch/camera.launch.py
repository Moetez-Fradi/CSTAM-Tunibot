from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.conditions import UnlessCondition
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from os.path import join

pkg = get_package_share_directory('andino_bringup')

def generate_launch_description():
    use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true')

    intrinsic_params_file = DeclareLaunchArgument(
        'intrinsic_params_file',
        default_value='file://' + join(pkg, 'config', 'raspicam.yaml')
    )

    image_size = DeclareLaunchArgument('image_size', default_value='[320, 240]')
    fps = DeclareLaunchArgument('fps', default_value='10')
    fmt = DeclareLaunchArgument('format', default_value='BGR888')

    width = PythonExpression(["int(", LaunchConfiguration('image_size'), "[0])"])
    height = PythonExpression(["int(", LaunchConfiguration('image_size'), "[1])"])

    frame_us = PythonExpression([
        "0 if int(", LaunchConfiguration('fps'),
        ")<=0 else int(1000000/int(", LaunchConfiguration('fps'), "))"
    ])

    frame_duration_limits = PythonExpression([
        "[] if int(", LaunchConfiguration('fps'),
        ")<=0 else [", frame_us, ",", frame_us, "]"
    ])

    return LaunchDescription([
        use_sim_time, intrinsic_params_file, image_size, fps, fmt,
        Node(
            package='camera_ros',
            executable='camera_node',
            name='camera',
            output='screen',
            parameters=[{
                'camera': '/base/soc/i2c0mux/i2c@1/imx219@10',
                'format': LaunchConfiguration('format'),
                'width': width,
                'height': height,
                'FrameDurationLimits': frame_duration_limits,
                'frame_id': 'camera_Link',
                'camera_info_url': LaunchConfiguration('intrinsic_params_file'),
                'jpeg_quality': 30,
            }],
            condition=UnlessCondition(LaunchConfiguration('use_sim_time')),
            remappings=[
                ('/camera/camera_info', '/camera_info'),
            ],
        )
    ])
