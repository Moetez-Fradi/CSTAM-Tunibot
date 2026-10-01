from glob import glob
import os

from setuptools import setup


package_name = 'cstam_phase1'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml') + glob('config/*.xml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'maps', 'restaurant'),
         glob('maps/restaurant/*')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*')),
        (os.path.join('share', package_name, 'scripts'), glob('scripts/*')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='CSTAM robot team',
    maintainer_email='maintainer@example.com',
    description='First-floor CSTAM Phase 1 autonomy MVP.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'delivery_task_manager = cstam_phase1.delivery_task_manager:main',
            'initial_pose_publisher = cstam_phase1.initial_pose_publisher:main',
            'mapping_route = cstam_phase1.mapping_route:main',
            'scan_self_filter = cstam_phase1.scan_self_filter:main',
            'pointcloud_navigation_filter = cstam_phase1.pointcloud_navigation_filter:main',
            'startup_health_check = cstam_phase1.startup_health_check:main',
        ],
    },
)
