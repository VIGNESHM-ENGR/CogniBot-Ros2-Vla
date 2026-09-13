"""CogniBot robots as LeRobot plugins (discovered by the `lerobot_robot_` prefix)."""

from .cognibot import CognibotPanda, CognibotSO101
from .config_cognibot import CognibotPandaConfig, CognibotSO101Config

__all__ = ["CognibotPanda", "CognibotPandaConfig", "CognibotSO101", "CognibotSO101Config"]
