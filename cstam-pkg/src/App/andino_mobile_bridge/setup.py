from setuptools import setup
from glob import glob
package_name = 'andino_mobile_bridge'
setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py'))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='You',
    maintainer_email='you@example.com',
    description='Bridge mobile app data to robot',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'mobile_bridge = andino_mobile_bridge.mobile_bridge:main',
            'topic_monitor = andino_mobile_bridge.topic_monitor:main',
            'phone_qr_sender = andino_mobile_bridge.phone_qr_sender:main'
        ],
    },
)
