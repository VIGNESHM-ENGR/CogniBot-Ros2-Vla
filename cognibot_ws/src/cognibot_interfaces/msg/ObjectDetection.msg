std_msgs/Header header                  # image header (camera optical frame, stamp)
string label
float32 confidence                      # 0..1, or -1 if the model gives none
int32[4] bbox_xyxy                      # pixels in the source image
geometry_msgs/PointStamped position     # in robot base frame when has_position
bool has_position
