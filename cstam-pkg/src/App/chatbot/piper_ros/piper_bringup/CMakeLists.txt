cmake_minimum_required(VERSION 3.8)
project(piper_bringup)

# find dependencies
find_package(ament_cmake REQUIRED)

install(DIRECTORY
  launch
  DESTINATION share/${PROJECT_NAME}/
)

install(PROGRAMS
  scripts/start_piper.py
  scripts/audio_bridge.py
  scripts/simple_player.py
  DESTINATION lib/${PROJECT_NAME}/
)

ament_package()
