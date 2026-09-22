# One GPU model's residency, published (transient local) by the node that owns it: the VLM agent
# (Qwen3-VL through llama-swap), the skill executor (the LeRobot policy) and the RLCD decision node
# (Laya). The dashboard shows them on the GPU gauge and warns while one is loading or unloading.
uint8 UNLOADED=0
uint8 LOADING=1
uint8 LOADED=2
uint8 UNLOADING=3

std_msgs/Header header
string name          # vlm | vla | rlcd
string model         # what is (or will be) resident, e.g. "Qwen3-VL-4B", "smolvla_arena_multitask"
uint8 state
string detail        # why it changed, e.g. "freed for a VLA run"
