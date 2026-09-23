/**
 * Free-look mirror of the simulation: the simulator's own MJCF loaded into MuJoCo WASM for
 * kinematics only (no physics), drawn with three.js. Joint and object states come from ROS;
 * frames render on demand so an idle view costs no GPU.
 */
import loadMujoco, { type MainModule, type MjData, type MjModel } from "@mujoco/mujoco";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export interface SceneManifest {
  robot: string;
  scene: string;
  assets: string[];
  tintMaterials: string[];
}

export interface ObjectPose {
  name: string;
  position: [number, number, number];
  quaternion: [number, number, number, number]; // w, x, y, z
}

const ROBOT_RED = new THREE.Color(0.72, 0.07, 0.07);
const FLOOR_SPAN = 2; // metres of bench top drawn under the arm, 5 cm grid squares
const MAX_VISUAL_GROUP = 2;

export class SceneMirror {
  private mj!: MainModule;
  private model!: MjModel;
  private data!: MjData;
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(45, 1, 0.01, 50);
  private controls: OrbitControls;
  private geoms: { index: number; object: THREE.Mesh }[] = [];
  private jointAdr = new Map<string, number>();
  private freeAdr = new Map<string, number>();
  private frame = 0;
  private resizeObserver: ResizeObserver;
  private disposed = false;

  constructor(private host: HTMLElement) {
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    this.renderer.setClearColor(0x0a0d0e);
    host.appendChild(this.renderer.domElement);

    this.camera.up.set(0, 0, 1);
    this.camera.position.set(0.75, -0.55, 0.45);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(0.2, 0.05, 0.05);
    this.controls.enableDamping = false;
    this.controls.addEventListener("change", () => this.requestRender());
    this.controls.update();

    // A white bench top under the arm: the robot, the green cube and the black target all read
    // against it on a screen recording, and the 5 cm grid gives the scale the scene has no ruler for.
    this.scene.add(new THREE.HemisphereLight(0xdfe6ea, 0x9aa1a0, 1.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(1, -1, 2);
    this.scene.add(key);
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(FLOOR_SPAN, FLOOR_SPAN),
      new THREE.MeshStandardMaterial({ color: 0xf1f2ee, roughness: 0.95, metalness: 0 }),
    );
    floor.position.z = -0.002;
    this.scene.add(floor);
    const grid = new THREE.GridHelper(FLOOR_SPAN, FLOOR_SPAN / 0.05, 0x4c565b, 0x9aa4a8);
    grid.rotation.x = Math.PI / 2;
    this.scene.add(grid);

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(host);
    this.resize();
  }

  async load(baseUrl: string): Promise<void> {
    const manifest: SceneManifest = await (await fetch(`${baseUrl}/manifest.json`)).json();
    this.mj = await loadMujoco();
    const fs = (
      this.mj as unknown as {
        FS: {
          mkdirTree: (p: string) => void;
          writeFile: (p: string, d: Uint8Array | string) => void;
        };
      }
    ).FS;
    fs.mkdirTree("/sim/assets");
    const [xml, ...meshes] = await Promise.all([
      fetch(`${baseUrl}/${manifest.scene}`).then((r) => r.text()),
      ...manifest.assets.map((f) => fetch(`${baseUrl}/assets/${f}`).then((r) => r.arrayBuffer())),
    ]);
    fs.writeFile("/sim/scene.xml", xml as string);
    manifest.assets.forEach((file, i) =>
      fs.writeFile(`/sim/assets/${file}`, new Uint8Array(meshes[i] as ArrayBuffer)),
    );
    if (this.disposed) return;
    this.model = this.mj.MjModel.from_xml_path("/sim/scene.xml");
    this.data = new this.mj.MjData(this.model);
    this.indexJoints();
    this.buildGeoms(new Set(manifest.tintMaterials));
    this.mj.mj_kinematics(this.model, this.data);
    this.syncGeoms();
    this.requestRender();
  }

  /** Apply arm joints and object poses from the same instant, then render once. */
  setState(names: string[], positions: number[], objects: ObjectPose[]): void {
    if (!this.model) return;
    const qpos = this.data.qpos as Float64Array;
    names.forEach((name, i) => {
      const adr = this.jointAdr.get(name);
      if (adr !== undefined) qpos[adr] = positions[i] ?? 0;
    });
    for (const obj of objects) {
      const adr = this.freeAdr.get(obj.name);
      if (adr !== undefined) qpos.set([...obj.position, ...obj.quaternion], adr);
    }
    this.mj.mj_kinematics(this.model, this.data);
    this.syncGeoms();
    this.requestRender();
  }

  resetView(): void {
    this.camera.position.set(0.75, -0.55, 0.45);
    this.controls.target.set(0.2, 0.05, 0.05);
    this.controls.update();
  }

  dispose(): void {
    this.disposed = true;
    cancelAnimationFrame(this.frame);
    this.resizeObserver.disconnect();
    this.controls.dispose();
    for (const { object } of this.geoms) {
      object.geometry.dispose();
      (object.material as THREE.Material).dispose();
    }
    this.renderer.dispose();
    this.renderer.domElement.remove();
    this.data?.delete();
    this.model?.delete();
  }

  private requestRender(): void {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.renderer.render(this.scene, this.camera);
    });
  }

  private resize(): void {
    const { clientWidth: w, clientHeight: h } = this.host;
    if (w === 0 || h === 0) return;
    this.renderer.setSize(w, h, false);
    this.renderer.domElement.style.width = "100%";
    this.renderer.domElement.style.height = "100%";
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.requestRender();
  }

  private name(adr: number): string {
    const names = this.model.names as Uint8Array;
    let end = adr;
    while (names[end] !== 0) end++;
    return new TextDecoder().decode(names.subarray(adr, end));
  }

  private indexJoints(): void {
    const jntType = this.model.jnt_type as Int32Array;
    const jntAdr = this.model.jnt_qposadr as Int32Array;
    const bodyJnt = this.model.body_jntadr as Int32Array;
    for (let j = 0; j < this.model.njnt; j++) {
      const name = this.mj.mj_id2name(this.model, this.mj.mjtObj.mjOBJ_JOINT.value, j);
      if (jntType[j] === this.mj.mjtJoint.mjJNT_FREE.value) continue;
      this.jointAdr.set(name, jntAdr[j] as number);
    }
    for (let b = 0; b < this.model.nbody; b++) {
      const j = bodyJnt[b] as number;
      if (j < 0 || jntType[j] !== this.mj.mjtJoint.mjJNT_FREE.value) continue;
      this.freeAdr.set(
        this.mj.mj_id2name(this.model, this.mj.mjtObj.mjOBJ_BODY.value, b),
        jntAdr[j] as number,
      );
    }
  }

  private buildGeoms(tint: Set<string>): void {
    const m = this.model;
    const types = m.geom_type as Int32Array;
    const groups = m.geom_group as Int32Array;
    const dataId = m.geom_dataid as Int32Array;
    const matId = m.geom_matid as Int32Array;
    const geomRgba = m.geom_rgba as Float32Array;
    const matRgba = m.mat_rgba as Float32Array;
    const size = m.geom_size as Float64Array;
    const matNames = m.name_matadr as Int32Array;
    const G = this.mj.mjtGeom;

    for (let g = 0; g < m.ngeom; g++) {
      if ((groups[g] as number) > MAX_VISUAL_GROUP) continue;
      const type = types[g] as number;
      const [sx, sy, sz] = [size[g * 3] ?? 0, size[g * 3 + 1] ?? 0, size[g * 3 + 2] ?? 0];
      let geometry: THREE.BufferGeometry;
      if (type === G.mjGEOM_MESH.value) geometry = this.meshGeometry(dataId[g] as number);
      else if (type === G.mjGEOM_BOX.value)
        geometry = new THREE.BoxGeometry(2 * sx, 2 * sy, 2 * sz);
      else if (type === G.mjGEOM_SPHERE.value) geometry = new THREE.SphereGeometry(sx, 24, 16);
      else if (type === G.mjGEOM_CYLINDER.value)
        geometry = new THREE.CylinderGeometry(sx, sx, 2 * sy, 32).rotateX(Math.PI / 2);
      else if (type === G.mjGEOM_CAPSULE.value)
        geometry = new THREE.CapsuleGeometry(sx, 2 * sy, 8, 16).rotateX(Math.PI / 2);
      else continue; // planes: the bench top and its grid stand in for the floor

      const mat = matId[g] as number;
      const rgba =
        mat >= 0 ? matRgba.subarray(mat * 4, mat * 4 + 4) : geomRgba.subarray(g * 4, g * 4 + 4);
      const color = new THREE.Color(rgba[0] ?? 1, rgba[1] ?? 1, rgba[2] ?? 1);
      if (mat >= 0 && tint.has(this.name(matNames[mat] as number))) color.copy(ROBOT_RED);
      const material = new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.05 });
      const object = new THREE.Mesh(geometry, material);
      object.matrixAutoUpdate = false;
      this.scene.add(object);
      this.geoms.push({ index: g, object });
    }
  }

  private meshGeometry(mesh: number): THREE.BufferGeometry {
    const m = this.model;
    const vertAdr = (m.mesh_vertadr as Int32Array)[mesh] as number;
    const vertNum = (m.mesh_vertnum as Int32Array)[mesh] as number;
    const faceAdr = (m.mesh_faceadr as Int32Array)[mesh] as number;
    const faceNum = (m.mesh_facenum as Int32Array)[mesh] as number;
    const positions = new Float32Array(
      (m.mesh_vert as Float32Array).subarray(vertAdr * 3, (vertAdr + vertNum) * 3),
    );
    const faces = new Uint32Array(
      (m.mesh_face as Int32Array).subarray(faceAdr * 3, (faceAdr + faceNum) * 3),
    );
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setIndex(new THREE.BufferAttribute(faces, 1));
    geometry.computeVertexNormals();
    return geometry;
  }

  private syncGeoms(): void {
    const xpos = this.data.geom_xpos as Float64Array;
    const xmat = this.data.geom_xmat as Float64Array;
    for (const { index: g, object } of this.geoms) {
      const p = g * 3;
      const r = g * 9;
      object.matrix.set(
        xmat[r] as number,
        xmat[r + 1] as number,
        xmat[r + 2] as number,
        xpos[p] as number,
        xmat[r + 3] as number,
        xmat[r + 4] as number,
        xmat[r + 5] as number,
        xpos[p + 1] as number,
        xmat[r + 6] as number,
        xmat[r + 7] as number,
        xmat[r + 8] as number,
        xpos[p + 2] as number,
        0,
        0,
        0,
        1,
      );
    }
  }
}
