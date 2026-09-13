"""Robot registry schema and loader.

Parses robot.yaml specifications into frozen dataclasses, resolving relative paths
against the cognibot_sim share or source directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
except ImportError:
    PackageNotFoundError = Exception  # type: ignore[misc, assignment]
    get_package_share_directory = None  # type: ignore[assignment]


class RobotRegistryError(ValueError):
    """Raised when a robot configuration is invalid, missing keys, or cannot be found."""


@dataclass(frozen=True)
class GripperConfig:
    joint: str
    open: float
    closed: float


@dataclass(frozen=True)
class MJCFConfig:
    scene: Path
    ik_model: Path
    tint_materials: tuple[str, ...] = ()


@dataclass(frozen=True)
class MoveItConfig:
    config_package: str
    kinematics_override: Path


@dataclass(frozen=True)
class CameraConfig:
    topic: str
    frame: str
    depth: bool = False


@dataclass(frozen=True)
class SafetyConfig:
    collision_spheres: Path
    min_distance: float
    max_joint_velocity: float


@dataclass(frozen=True)
class WorkspaceSphereConfig:
    center: tuple[float, float, float]
    r_min: float
    r_max: float


@dataclass(frozen=True)
class ReachConfig:
    study_dir: Path
    workspace_sphere: WorkspaceSphereConfig


@dataclass(frozen=True)
class VLAConfig:
    lerobot_robot_type: str
    checkpoint: str


@dataclass(frozen=True)
class RobotConfig:
    name: str
    base_frame: str
    ee_frame: str
    ee_site: str
    arm_joints: tuple[str, ...]
    gripper: GripperConfig
    home_pose: tuple[float, ...]
    mjcf: MJCFConfig
    urdf: Path
    controllers: Path
    moveit: MoveItConfig
    cameras: dict[str, CameraConfig]
    safety: SafetyConfig
    reach: ReachConfig
    vla: VLAConfig


def find_sim_share_dir() -> Path:
    """Find the cognibot_sim share or source directory."""
    if get_package_share_directory is not None:
        try:
            return Path(get_package_share_directory("cognibot_sim"))
        except PackageNotFoundError:
            pass

    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "cognibot_sim"
        if candidate.is_dir() and (candidate / "package.xml").is_file():
            return candidate
        candidate_ws = parent / "cognibot_ws" / "src" / "cognibot_sim"
        if candidate_ws.is_dir() and (candidate_ws / "package.xml").is_file():
            return candidate_ws

    raise RobotRegistryError(
        "Could not locate 'cognibot_sim' package share or source directory. "
        "Ensure ROS workspace is sourced or pass registry_path explicitly."
    )


def _require_key(data: dict[str, Any], key: str, context: str = "") -> Any:
    if not isinstance(data, dict):
        ctx = f" in {context}" if context else ""
        raise RobotRegistryError(f"Expected a dictionary{ctx}, got {type(data).__name__}")
    if key not in data:
        ctx = f" in {context}" if context else ""
        raise RobotRegistryError(f"Missing required key '{key}'{ctx}")
    return data[key]


def _resolve_path(path_str: str, base_dir: Path) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def parse_robot_config(data: dict[str, Any], base_dir: Path) -> RobotConfig:
    """Parse a dictionary into a RobotConfig, resolving paths against base_dir."""
    if not isinstance(data, dict):
        raise RobotRegistryError(f"Configuration must be a dictionary, got {type(data).__name__}")

    name = str(_require_key(data, "name"))
    base_frame = str(_require_key(data, "base_frame", name))
    ee_frame = str(_require_key(data, "ee_frame", name))
    ee_site = str(_require_key(data, "ee_site", name))

    raw_arm_joints = _require_key(data, "arm_joints", name)
    if not isinstance(raw_arm_joints, (list, tuple)):
        raise RobotRegistryError(f"'arm_joints' in {name} must be a list of strings")
    arm_joints = tuple(str(j) for j in raw_arm_joints)

    raw_gripper = _require_key(data, "gripper", name)
    gripper = GripperConfig(
        joint=str(_require_key(raw_gripper, "joint", f"{name}.gripper")),
        open=float(_require_key(raw_gripper, "open", f"{name}.gripper")),
        closed=float(_require_key(raw_gripper, "closed", f"{name}.gripper")),
    )

    raw_home_pose = _require_key(data, "home_pose", name)
    if not isinstance(raw_home_pose, (list, tuple)):
        raise RobotRegistryError(f"'home_pose' in {name} must be a list of floats")
    home_pose = tuple(float(x) for x in raw_home_pose)

    raw_mjcf = _require_key(data, "mjcf", name)
    mjcf = MJCFConfig(
        scene=_resolve_path(_require_key(raw_mjcf, "scene", f"{name}.mjcf"), base_dir),
        ik_model=_resolve_path(_require_key(raw_mjcf, "ik_model", f"{name}.mjcf"), base_dir),
        tint_materials=tuple(str(m) for m in raw_mjcf.get("tint_materials", ())),
    )

    urdf = _resolve_path(_require_key(data, "urdf", name), base_dir)
    controllers = _resolve_path(_require_key(data, "controllers", name), base_dir)

    raw_moveit = _require_key(data, "moveit", name)
    moveit = MoveItConfig(
        config_package=str(_require_key(raw_moveit, "config_package", f"{name}.moveit")),
        kinematics_override=_resolve_path(
            _require_key(raw_moveit, "kinematics_override", f"{name}.moveit"), base_dir
        ),
    )

    raw_cameras = _require_key(data, "cameras", name)
    if not isinstance(raw_cameras, dict):
        raise RobotRegistryError(f"'cameras' in {name} must be a dictionary")
    cameras: dict[str, CameraConfig] = {}
    for cam_name, cam_data in raw_cameras.items():
        cameras[cam_name] = CameraConfig(
            topic=str(_require_key(cam_data, "topic", f"{name}.cameras.{cam_name}")),
            frame=str(_require_key(cam_data, "frame", f"{name}.cameras.{cam_name}")),
            depth=bool(cam_data.get("depth", False)),
        )

    raw_safety = _require_key(data, "safety", name)
    safety = SafetyConfig(
        collision_spheres=_resolve_path(
            _require_key(raw_safety, "collision_spheres", f"{name}.safety"), base_dir
        ),
        min_distance=float(_require_key(raw_safety, "min_distance", f"{name}.safety")),
        max_joint_velocity=float(_require_key(raw_safety, "max_joint_velocity", f"{name}.safety")),
    )

    raw_reach = _require_key(data, "reach", name)
    raw_ws = _require_key(raw_reach, "workspace_sphere", f"{name}.reach")
    raw_center = _require_key(raw_ws, "center", f"{name}.reach.workspace_sphere")
    if not isinstance(raw_center, (list, tuple)) or len(raw_center) != 3:
        raise RobotRegistryError(
            f"'center' in {name}.reach.workspace_sphere must be a 3-element list/tuple"
        )
    ws_sphere = WorkspaceSphereConfig(
        center=(float(raw_center[0]), float(raw_center[1]), float(raw_center[2])),
        r_min=float(_require_key(raw_ws, "r_min", f"{name}.reach.workspace_sphere")),
        r_max=float(_require_key(raw_ws, "r_max", f"{name}.reach.workspace_sphere")),
    )
    reach = ReachConfig(
        study_dir=_resolve_path(_require_key(raw_reach, "study_dir", f"{name}.reach"), base_dir),
        workspace_sphere=ws_sphere,
    )

    raw_vla = _require_key(data, "vla", name)
    vla = VLAConfig(
        lerobot_robot_type=str(_require_key(raw_vla, "lerobot_robot_type", f"{name}.vla")),
        checkpoint=str(_require_key(raw_vla, "checkpoint", f"{name}.vla")),
    )

    return RobotConfig(
        name=name,
        base_frame=base_frame,
        ee_frame=ee_frame,
        ee_site=ee_site,
        arm_joints=arm_joints,
        gripper=gripper,
        home_pose=home_pose,
        mjcf=mjcf,
        urdf=urdf,
        controllers=controllers,
        moveit=moveit,
        cameras=cameras,
        safety=safety,
        reach=reach,
        vla=vla,
    )


def load_robot(
    name: str,
    registry_path: Path | str | None = None,
    sim_share_dir: Path | str | None = None,
) -> RobotConfig:
    """Load and parse robot configuration for the given robot name.

    Args:
        name: Name of the robot (e.g. 'so101' or 'panda').
        registry_path: Explicit path to the robot.yaml file. If provided,
            overrides the default path lookup.
        sim_share_dir: Explicit path to cognibot_sim share/source directory.
            If None, inferred automatically.

    Returns:
        A validated RobotConfig frozen dataclass instance.
    """
    if sim_share_dir is not None:
        base_dir = Path(sim_share_dir).resolve()
    else:
        try:
            base_dir = find_sim_share_dir()
        except RobotRegistryError:
            if registry_path is not None:
                p = Path(registry_path).resolve()
                # .../cognibot_sim/robots/so101/robot.yaml -> base_dir is .../cognibot_sim
                if "robots" in p.parts:
                    idx = p.parts.index("robots")
                    base_dir = Path(*p.parts[:idx])
                else:
                    base_dir = p.parent
            else:
                raise

    if registry_path is not None:
        yaml_path = Path(registry_path).resolve()
    else:
        yaml_path = (base_dir / "robots" / name / "robot.yaml").resolve()

    if not yaml_path.is_file():
        raise RobotRegistryError(
            f"Robot configuration file not found: {yaml_path} for robot '{name}'"
        )

    try:
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        raise RobotRegistryError(f"Failed to read/parse YAML from {yaml_path}: {exc}") from exc

    return parse_robot_config(data, base_dir)
