from setuptools import find_packages, setup
package_name = 'order_logger'
setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'jinja2', 'pandas', 'streamlit', 'plotly', 'fpdf', 'matplotlib'],
    zip_safe=True,
    maintainer='mo',
    maintainer_email='mohamed.bn.nasser2001@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'order_logger_node = order_logger.order_logger_node:main',
        ],
    },
)
