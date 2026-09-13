uint8 THOUGHT=0
uint8 TOOL_CALL=1
uint8 TOOL_RESULT=2
uint8 INFO=3
uint8 ERROR=4
uint8 DONE=5

std_msgs/Header header
string task_id
uint32 step
uint8 type
string tool_name        # set for TOOL_CALL / TOOL_RESULT
string content          # free text or JSON (tool args / tool result)
float32 duration_s      # model or tool latency for this step
