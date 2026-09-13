import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ACTIONS,
  CUBE_HALF,
  DEMO,
  MOVEIT,
  ROSBRIDGE_URL,
  SERVICES,
  TOPICS,
  cubeBody,
  type CubeColor,
} from "./config";
import { toSeconds } from "./lib/duration";
import { holdGoal, jointGoal, MOVEIT_ERRORS, nudgeInsideLimits, pointGoal } from "./lib/goals";
import {
  commandForKey,
  jogForKey,
  MODES,
  nextSource,
  type Mode,
  type SourceId,
  type ViewId,
} from "./lib/modes";
import { parseSrdfGroupStates, parseUrdf, type GroupState } from "./lib/robotModel";
import { EStop } from "./pendant/EStop";
import { GpuGauge } from "./pendant/GpuGauge";
import { JogBlock } from "./pendant/JogBlock";
import { JointReadout } from "./pendant/JointReadout";
import { ModeKey } from "./pendant/ModeKey";
import { ProgramLine, type ProgramState } from "./pendant/ProgramLine";
import { SoftKeys } from "./pendant/SoftKeys";
import { StatusStrip } from "./pendant/StatusStrip";
import {
  useActionGoal,
  useGraph,
  useServiceCall,
  useTopic,
  useTopicRate,
  type GoalRun,
} from "./ros/hooks";
import type {
  Clock,
  ControlModeMsg,
  FollowJointTrajectoryFeedback,
  FollowJointTrajectoryGoal,
  FreeJointStateArray,
  GpuStatus,
  JointState,
  ResultMessage,
  SetControlModeResponse,
  SetFreeJointStateRequest,
  StageFeedback,
  StringMsg,
} from "./ros/messages";
import { RosProvider, useRos } from "./ros/RosProvider";
import { CameraView } from "./views/CameraView";
import { MotionView } from "./views/MotionView";
import { NotRunning } from "./views/NotRunning";
import { SystemView } from "./views/SystemView";
import { VlaView } from "./views/VlaView";
import { useKeyboardTeleop } from "./teleop/useKeyboardTeleop";

interface MoveGroupFeedback {
  state: string;
}
interface MoveGroupResult {
  error_code: { val: number };
}

const latest = <T,>(...runs: (GoalRun<T> | null)[]) =>
  runs.reduce<GoalRun<T> | null>((a, b) => (b && (!a || b.startedAt > a.startedAt) ? b : a), null);

function Pendant() {
  const { link, url } = useRos();
  const [localMode, setLocalMode] = useState<Mode>("IDLE");
  const [modeNotice, setModeNotice] = useState<string | undefined>();
  const [view, setView] = useState<ViewId>("camera");
  const [source, setSource] = useState<SourceId>("free");
  const [cube, setCube] = useState<CubeColor>("green");
  const [stopped, setStopped] = useState(false);

  const joints = useTopic<JointState>(TOPICS.jointStates, "sensor_msgs/msg/JointState", 100);
  const jointRate = useTopicRate(TOPICS.jointStates, "sensor_msgs/msg/JointState");
  const command = useTopic<JointState>(TOPICS.jointCommand, "sensor_msgs/msg/JointState", 200);
  const commandRate = useTopicRate(TOPICS.jointCommand, "sensor_msgs/msg/JointState");
  const clock = useTopic<Clock>(TOPICS.clock, "rosgraph_msgs/msg/Clock", 250);
  const gpu = useTopic<GpuStatus>(TOPICS.gpu, "cognibot_interfaces/msg/GpuStatus", 1000);
  const urdfMsg = useTopic<StringMsg>(TOPICS.robotDescription, "std_msgs/msg/String");
  const srdfMsg = useTopic<StringMsg>(TOPICS.robotDescriptionSemantic, "std_msgs/msg/String");
  const { services, topics, actions } = useGraph();
  const modeMsg = useTopic<ControlModeMsg>(TOPICS.mode, "cognibot_interfaces/msg/ControlMode");
  const setModeService = useServiceCall<
    { mode: number; requester: string; reason: string },
    SetControlModeResponse
  >(SERVICES.setMode, "cognibot_interfaces/srv/SetControlMode");

  const urdf = useMemo(() => (urdfMsg ? parseUrdf(urdfMsg.data) : null), [urdfMsg]);
  const groupStates = useMemo(() => (srdfMsg ? parseSrdfGroupStates(srdfMsg.data) : []), [srdfMsg]);

  const trajectory = useActionGoal<
    FollowJointTrajectoryGoal,
    FollowJointTrajectoryFeedback,
    unknown
  >(ACTIONS.trajectory, "control_msgs/action/FollowJointTrajectory");
  const moveGroup = useActionGoal<object, MoveGroupFeedback, MoveGroupResult>(
    ACTIONS.moveGroup,
    "moveit_msgs/action/MoveGroup",
  );
  const gripper = useActionGoal<object, unknown, unknown>(
    ACTIONS.gripper,
    "control_msgs/action/ParallelGripperCommand",
  );
  const fetchObject = useActionGoal<object, StageFeedback, ResultMessage>(
    ACTIONS.fetch,
    "cognibot_interfaces/action/FetchObject",
  );
  const placeObject = useActionGoal<object, StageFeedback, ResultMessage>(
    ACTIONS.place,
    "cognibot_interfaces/action/PlaceObject",
  );
  const resetObjects = useServiceCall<object, ResultMessage>(
    SERVICES.resetObjects,
    "std_srvs/srv/Trigger",
  );
  const setFreeJointState = useServiceCall<SetFreeJointStateRequest, ResultMessage>(
    SERVICES.setFreeJointState,
    "mujoco_ros2_control_msgs/srv/SetFreeJointState",
  );
  // Bodies can't be added to a running MuJoCo model: spawning teleports a parked cube.
  const spawnCube = (x: number, y: number) =>
    setFreeJointState({
      free_joints: [
        {
          name: cubeBody(cube),
          pose: {
            header: { frame_id: "world" },
            pose: { position: { x, y, z: CUBE_HALF }, orientation: { x: 0, y: 0, z: 0, w: 1 } },
          },
          twist: {
            header: { frame_id: "world" },
            twist: { linear: { x: 0, y: 0, z: 0 }, angular: { x: 0, y: 0, z: 0 } },
          },
        },
      ],
    }).then(
      (r) => setModeNotice(r.success ? undefined : r.message),
      (e: unknown) => setModeNotice(String(e)),
    );
  const objectPoses = useTopic<FreeJointStateArray>(
    TOPICS.objectPoses,
    "mujoco_ros2_control_msgs/msg/FreeJointStateArray",
    250,
  );
  const demoObject = objectPoses?.free_joints.find((o) => o.name === cubeBody(cube));

  const moveitOnline = actions.has(ACTIONS.moveGroup);
  const trajectoryOnline = actions.has(ACTIONS.trajectory);
  const gripperOnline = actions.has(ACTIONS.gripper);
  const managerOnline = services.has(SERVICES.setMode);
  // With the mode manager running the key shows the arbitrated mode; without it, a local one.
  const mode: Mode = managerOnline && modeMsg ? (MODES[modeMsg.mode] ?? "IDLE") : localMode;
  const setMode = useCallback(
    (target: Mode, reason = "mode key") => {
      if (!managerOnline) {
        setLocalMode(target);
        return;
      }
      setModeService({ mode: MODES.indexOf(target), requester: "dashboard", reason }).then(
        (r) => setModeNotice(r.success ? undefined : r.message),
        (e: unknown) => setModeNotice(String(e)),
      );
    },
    [managerOnline, setModeService],
  );
  useEffect(() => {
    if (!modeNotice) return;
    const t = setTimeout(() => setModeNotice(undefined), 5000);
    return () => clearTimeout(t);
  }, [modeNotice]);
  const pickPlaceOnline = actions.has(ACTIONS.fetch) && actions.has(ACTIONS.place);
  const teleopOnline = topics.has(TOPICS.teleopTarget);

  const describeMoveIt = (r: MoveGroupResult) =>
    MOVEIT_ERRORS[r.error_code.val] ?? `code ${r.error_code.val}`;

  const cancelAll = useCallback(() => {
    trajectory.cancel();
    moveGroup.cancel();
    gripper.cancel();
    fetchObject.cancel();
    placeObject.cancel();
  }, [trajectory, moveGroup, gripper, fetchObject, placeObject]);

  const describeResult = (r: ResultMessage) => r.message;
  /** Send a MoveGroup goal, first easing any joint parked on a limit back inside it. */
  const plan = (label: string, goal: object) => {
    const state = jointsRef.current;
    const armLimits = urdf?.joints.filter((j) => j.name !== "gripper") ?? [];
    const nudge = state ? nudgeInsideLimits(armLimits, state.name, state.position) : null;
    if (nudge && trajectoryOnline) {
      trajectory.send(
        "Ease off joint limit",
        holdGoal(nudge.names, nudge.positions, 0.5),
        undefined,
        () => moveGroup.send(label, goal, describeMoveIt),
      );
    } else {
      moveGroup.send(label, goal, describeMoveIt);
    }
  };
  const pickAndPlace = () =>
    fetchObject.send(
      `Pick ${cubeBody(cube)}`,
      { target: { header: { frame_id: cubeBody(cube) }, point: { x: 0, y: 0, z: 0 } } },
      describeResult,
      () =>
        placeObject.send(
          `Place on ${DEMO.target}`,
          { target: { header: { frame_id: DEMO.target }, point: { x: 0, y: 0, z: 0 } } },
          describeResult,
        ),
    );

  const jointsRef = useRef(joints);
  useEffect(() => {
    jointsRef.current = joints;
  }, [joints]);

  const jogEnabled = mode === "TELEOP" && !stopped;
  const jog = useKeyboardTeleop(jogEnabled, MOVEIT.base);

  const stop = useCallback(() => {
    cancelAll();
    setStopped(true);
    setMode("IDLE", "stop");
    const state = jointsRef.current;
    const armNames = urdf?.joints.map((j) => j.name).filter((n) => n !== "gripper") ?? [];
    if (state && trajectoryOnline && armNames.length > 0) {
      const positions = armNames.map((n) => state.position[state.name.indexOf(n)] ?? 0);
      trajectory.send("Hold after stop", holdGoal(armNames, positions));
    }
  }, [cancelAll, urdf, trajectoryOnline, trajectory, setMode]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const typing = target.tagName === "INPUT" || target.tagName === "TEXTAREA";
      const command = commandForKey(event.code, typing);
      if (!command) return;
      if (command.kind === "view" || command.kind === "jog") event.preventDefault();
      switch (command.kind) {
        case "stop":
          stop();
          break;
        case "release":
          setStopped(false);
          break;
        case "cancel":
          cancelAll();
          break;
        case "cycleSource":
          setSource((s) => nextSource(s));
          break;
        case "mode":
          setMode(command.mode);
          break;
        case "view":
          setView(command.view);
          break;
        case "jog":
          if (!event.repeat) jog.down(command.jog);
          break;
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      const released = jogForKey(event.code);
      if (released) jog.up(released);
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [stop, cancelAll, setMode, jog]);

  const run = latest<unknown>(
    trajectory.run as GoalRun<unknown> | null,
    moveGroup.run as GoalRun<unknown> | null,
    gripper.run as GoalRun<unknown> | null,
    fetchObject.run as GoalRun<unknown> | null,
    placeObject.run as GoalRun<unknown> | null,
  );
  const stageRun = [fetchObject.run, placeObject.run].find((r) => (r as unknown) === run);
  const moveGroupFeedback =
    run === (moveGroup.run as GoalRun<unknown> | null) ? moveGroup.run?.feedback : null;
  const program: ProgramState | null = run && {
    name: run.label,
    phase: run.phase,
    detail:
      run.phase === "active" && stageRun?.feedback
        ? `${stageRun.feedback.stage.replace("_", " ")} · ${Math.round(stageRun.feedback.progress * 100)}%`
        : run.phase === "active" && moveGroupFeedback?.state
          ? moveGroupFeedback.state.toLowerCase()
          : run.detail,
  };
  const commander =
    run?.phase === "active"
      ? run.label
      : mode === "VLA" && commandRate > 0
        ? `policy · ${modeMsg?.requester ?? "vla"}`
        : "no commander";
  const programActive = run?.phase === "active";
  const motionEnabled = mode === "MOTION" && !stopped && !programActive;
  const motionBlocked = stopped
    ? "Stopped: press Release (R) first."
    : programActive
      ? `${run.label} is running: wait or cancel (C) first.`
      : "Turn the mode key to MOTION (3) to plan and move.";

  return (
    <div className="room">
      <div className="pinned-stop">
        <button type="button" onClick={stop} aria-label="Stop: cancel every goal and hold the pose">
          STOP
        </button>
        <span className="legend">{stopped ? "Stopped · R" : "Esc"}</span>
      </div>
      <main className="housing">
        <aside className="grip">
          <div className="plate">
            <div className="plate__name">COGNIBOT</div>
            <div className="plate__sub">Operator pendant · {urdf?.robotName ?? "no robot"}</div>
          </div>
          <ModeKey
            mode={mode}
            onChange={setMode}
            managerOnline={managerOnline}
            notice={modeNotice}
          />
          <JogBlock
            mode={mode}
            pressed={jog.held}
            backendOnline={teleopOnline}
            stopped={stopped}
            onDown={jog.down}
            onUp={jog.up}
          />
        </aside>

        <div className="center">
          <div className="well">
            <StatusStrip
              link={link}
              url={url}
              robotName={urdf?.robotName ?? null}
              mode={mode}
              stopped={stopped}
              commander={commander}
              jointRate={jointRate}
              simTime={
                clock ? toSeconds({ sec: clock.clock.sec, nanosec: clock.clock.nanosec }) : null
              }
            />
            <div className="view">
              {view === "camera" && <CameraView source={source} onSource={setSource} />}
              {view === "motion" && (
                <MotionView
                  moveitOnline={moveitOnline}
                  gripperOnline={gripperOnline}
                  pickPlaceOnline={pickPlaceOnline}
                  resetOnline={services.has(SERVICES.resetObjects)}
                  objectPosition={
                    demoObject
                      ? [
                          demoObject.pose.pose.position.x,
                          demoObject.pose.pose.position.y,
                          demoObject.pose.pose.position.z,
                        ]
                      : null
                  }
                  source={source}
                  onPickPlace={pickAndPlace}
                  onReset={() => resetObjects({}).catch(() => undefined)}
                  cube={cube}
                  onCube={setCube}
                  onSpawn={spawnCube}
                  groupStates={groupStates}
                  enabled={motionEnabled}
                  blockedReason={motionBlocked}
                  onNamedPose={(s: GroupState) =>
                    plan(`Move to ${s.name}`, jointGoal(MOVEIT.arm, s.joints))
                  }
                  onGripper={(s: GroupState) =>
                    gripper.send(`Gripper ${s.name}`, {
                      command: {
                        name: Object.keys(s.joints),
                        position: Object.values(s.joints),
                        effort: [5.0],
                      },
                    })
                  }
                  onPoint={(p) =>
                    plan(
                      `Move to (${p.x.toFixed(2)}, ${p.y.toFixed(2)}, ${p.z.toFixed(2)})`,
                      pointGoal(MOVEIT.arm, MOVEIT.tip, MOVEIT.base, p),
                    )
                  }
                />
              )}
              {view === "agent" && (
                <NotRunning title="Language agent" missing="vlm-agent" start="make vlm">
                  Type a task such as “pick the green cube and put it on the blue target”. Qwen3-VL
                  grounds it in the front camera and calls motion and VLA tools; each tool call will
                  appear here as it runs.
                </NotRunning>
              )}
              {view === "vla" && (
                <VlaView
                  active={mode === "VLA"}
                  modeMsg={modeMsg}
                  command={command}
                  commandRate={commandRate}
                  joints={joints}
                />
              )}
              {view === "system" && <SystemView services={services} topics={topics} gpu={gpu} />}
            </div>
            <ProgramLine program={program} onCancel={cancelAll} />
          </div>
          <SoftKeys view={view} onView={setView} />
        </div>

        <aside className="grip">
          <EStop latched={stopped} onStop={stop} onRelease={() => setStopped(false)} />
          <div className="mini-well">
            <h2 className="legend">Joints</h2>
            <JointReadout limits={urdf?.joints ?? []} state={joints} />
          </div>
          <div className="mini-well">
            <h2 className="legend">GPU</h2>
            <GpuGauge status={gpu} />
          </div>
        </aside>
      </main>
    </div>
  );
}

export function App() {
  return (
    <RosProvider url={ROSBRIDGE_URL}>
      <Pendant />
    </RosProvider>
  );
}
