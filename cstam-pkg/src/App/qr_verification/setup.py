from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'qr_verification'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Jack',
    maintainer_email='admin@jackisaac.qzz.io',
    description='QR Verification Package that generates and scans a QR Code for delivery verification.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'qr_generator = qr_verification.qr_generator:main',
            'qr_scanner = qr_verification.qr_scanner:main',
        ],
    },
)
