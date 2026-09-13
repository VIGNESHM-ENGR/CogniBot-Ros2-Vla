uint8 IDLE=0
uint8 TELEOP=1
uint8 MOTION=2
uint8 VLA=3
uint8 TWIN=4

builtin_interfaces/Time stamp
uint8 mode
string requester        # node that requested the current mode
string reason
