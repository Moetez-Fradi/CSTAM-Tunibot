from glob import glob
import os

from setuptools import setup


package_name = 'cstam_ui'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'web'),
         [f for f in glob('web/*') if os.path.isfile(f)]),
        (os.path.join('share', package_name, 'web', 'fonts'), glob('web/fonts/*')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    tests_require=['pytest'],
    zip_safe=True,
    maintainer='CSTAM robot team',
    maintainer_email='maintainer@example.com',
    description='Customer ordering and admin monitoring web UI for CSTAM.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'ui_server = cstam_ui.ui_node:main',
        ],
    },
)
