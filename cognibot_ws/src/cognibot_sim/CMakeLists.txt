cmake_minimum_required(VERSION 3.22)
project(cognibot_sim)

find_package(ament_cmake REQUIRED)

# Install only the resource directories that exist, so the skeleton builds
# before every phase has added content.
foreach(dir launch config robots scenes scripts)
  if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/${dir})
    install(DIRECTORY ${dir} DESTINATION share/${PROJECT_NAME})
  endif()
endforeach()

ament_package()
