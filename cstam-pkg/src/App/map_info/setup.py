from glob import glob
from setuptools import setup
import os
package_name = 'map_info'
setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],  
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/maps', glob('maps/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mo',
    maintainer_email='you@example.com',  
    description='Named pose tools for DeliveryBot (goal_name, go_menu, app_goal_gateway).',
    license='TODO',  
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'goal_name = map_info.goal_name:main',
            'go_menu = map_info.go_menu:main',
            'app_goal_gateway = map_info.app_goal_gateway:main',
        ],
    },
)
