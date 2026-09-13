uint8 GRIPPER_NONE=0
uint8 GRIPPER_TOGGLE=1
uint8 GRIPPER_OPEN=2
uint8 GRIPPER_CLOSE=3

std_msgs/Header header          # frame_id: robot base frame
geometry_msgs/Vector3 linear    # normalized [-1, 1] per axis; scaled by node param max_linear_speed (m/s)
float64 wrist_roll              # normalized [-1, 1]; scaled by max_angular_speed (rad/s)
uint8 gripper                   # GRIPPER_* command (edge-triggered)
