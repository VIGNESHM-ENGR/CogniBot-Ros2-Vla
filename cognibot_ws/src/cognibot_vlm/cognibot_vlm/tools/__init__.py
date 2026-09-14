"""Robot capabilities exposed to the VLM as OpenAI-style tools (ADR-0007)."""

from cognibot_vlm.tools.schemas import TOOLS, ToolError, validate_arguments

__all__ = ["TOOLS", "ToolError", "validate_arguments"]
