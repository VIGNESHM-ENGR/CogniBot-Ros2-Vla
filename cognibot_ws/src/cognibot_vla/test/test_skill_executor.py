from cognibot_vla.skill_executor_node import stop_reason


def test_keeps_running_while_connecting_and_streaming():
    assert stop_reason(False, 1.0, 0.0, in_vla=False, entered_vla=False) is None
    assert stop_reason(False, 30.0, 0.0, in_vla=True, entered_vla=True) is None


def test_cancel_wins_over_everything():
    assert stop_reason(True, 0.0, 0.0, in_vla=True, entered_vla=True) == "canceled"


def test_duration_and_mode_loss():
    assert stop_reason(False, 60.0, 60.0, True, True) == "max_duration_s 60 reached"
    assert stop_reason(False, 5.0, 0.0, in_vla=False, entered_vla=True) == "arm left VLA mode"


def test_silent_policy_is_reported():
    assert stop_reason(False, 40.0, 0.0, True, True, silent_s=29.0) is None
    assert stop_reason(False, 40.0, 0.0, True, True, silent_s=30.0).startswith("no actions")
