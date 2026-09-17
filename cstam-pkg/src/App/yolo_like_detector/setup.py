import os
from glob import glob
from setuptools import setup

package_name = 'yolo_like_detector'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        # Standard ROS 2 resource files (required for installation)
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        
        # --- FIX: COPY LOCAL MODEL AND CONFIG FILES ---
        
        # This line copies the entire 'weights' folder (containing best.onnx)
        (os.path.join('share', package_name, 'weights'), glob('weights/*')),

        # This line copies the entire 'config' folder (containing data.yaml)
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        
        # --- END OF FIX ---
    ],
    install_requires=['setuptools', 'rclpy', 'onnxruntime'],
    zip_safe=True,
    maintainer='Your Name', 
    maintainer_email='your.email@example.com', 
    description='ROS 2 package for YOLO-based object detection using local ONNX model.',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'like_detector_node = yolo_like_detector.like_detector:main',
        ],
    },
)
