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

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_model_consistency test/test_model_consistency.py
    TIMEOUT 60
  )
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(test/test_sim_launch.py
    TIMEOUT 60
  )
  add_launch_test(test/test_camera_reprojection.py
    TIMEOUT 60
  )
  add_launch_test(test/test_panda_sim_launch.py
    TIMEOUT 60
  )
endif()

ament_package()
