#!/usr/bin/env python3
"""Calculate exact camera optical quaternion and verify projection."""

import numpy as np

# Camera axes in ROS optical convention
x_opt = np.array([0.0, 1.0, 0.0])  # image right (+Y in world)
y_opt = np.array([0.696, 0.0, -0.718])  # image down
z_opt = np.array([-0.718, 0.0, -0.696])  # forward / view ray

# Normalize to be exact
z_opt = z_opt / np.linalg.norm(z_opt)
x_opt = x_opt / np.linalg.norm(x_opt)
y_opt = np.cross(z_opt, x_opt)
y_opt = y_opt / np.linalg.norm(y_opt)

R = np.column_stack([x_opt, y_opt, z_opt])

# Convert R to quaternion [qx, qy, qz, qw]
tr = np.trace(R)
if tr > 0:
    S = np.sqrt(tr + 1.0) * 2
    qw = 0.25 * S
    qx = (R[2, 1] - R[1, 2]) / S
    qy = (R[0, 2] - R[2, 0]) / S
    qz = (R[1, 0] - R[0, 1]) / S
elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
    S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
    qw = (R[2, 1] - R[1, 2]) / S
    qx = 0.25 * S
    qy = (R[0, 1] + R[1, 0]) / S
    qz = (R[0, 2] + R[2, 0]) / S
elif R[1, 1] > R[2, 2]:
    S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
    qw = (R[0, 2] - R[2, 0]) / S
    qx = (R[0, 1] + R[1, 0]) / S
    qy = 0.25 * S
    qz = (R[1, 2] + R[2, 1]) / S
else:
    S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
    qw = (R[1, 0] - R[0, 1]) / S
    qx = (R[0, 2] + R[2, 0]) / S
    qy = (R[1, 2] + R[2, 1]) / S
    qz = 0.25 * S

q = np.array([qx, qy, qz, qw])
q /= np.linalg.norm(q)
print(f"R:\n{R}")
print(f"Quaternion [qx, qy, qz, qw]: {q.tolist()}")

# Test projection of cube pos [0.274100, -0.019501, 0.012445]
p_world = np.array([0.274100, -0.019501, 0.012445])
cam_pos = np.array([0.56, 0.08, 0.36])

# Point in camera optical frame
p_cam = R.T @ (p_world - cam_pos)
print(f"p_cam: {p_cam}")

# Intrinsics
fx = 539.04882574
fy = 539.04882574
cx = 320.0
cy = 240.0

u = fx * (p_cam[0] / p_cam[2]) + cx
v = fy * (p_cam[1] / p_cam[2]) + cy
print(f"Projected pixel (u, v): ({u:.2f}, {v:.2f})")
