set(CMAKE_SUPPRESS_DEVELOPER_WARNINGS 1 CACHE INTERNAL "No dev warnings")
cmake_minimum_required(VERSION 3.7)
project(andino_gz)

find_package(gazebo QUIET)
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# If the Python package directory andino_gz/ contains __init__.py, keep this.
# If not, you can comment it out safely.
ament_python_install_package("andino_gz")

# Install shared resources
install(
  DIRECTORY
    config
    config_gui
    models
    launch
    maps
    rviz
    urdf
    worlds
  DESTINATION
    share/${PROJECT_NAME}/
)



ament_package()

