# One typed decision taken by the RLCD decision layer (ADR-0008). Options and probabilities are
# parallel arrays so a viewer can draw the distribution the choice came from.
std_msgs/Header header
string task_id
uint32 step
string question_id      # skill | object | move | unsafe | out_of_scope | needs_human
string[] options
float32[] probabilities
string choice
float32 confidence      # calibrated, 0..1
float32 act_probability # act vs escalate head, 0..1
string model            # checkpoint that answered: english | multilingual | typed-decisions
float32 latency_ms
