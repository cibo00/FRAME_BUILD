<script setup lang="ts">
import { ref as vueRef, onMounted, watch, onUnmounted, computed } from 'vue'
import * as THREE from 'three'
import { Quaternion, Vector3,Vector2 } from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { DragControls } from 'three/examples/jsm/controls/DragControls.js'
import { FontLoader } from 'three/examples/jsm/loaders/FontLoader.js'
import { TextGeometry } from 'three/examples/jsm/geometries/TextGeometry.js'
import { BezierCurve } from '../utils/BezierUtils'
import { Const } from 'three/tsl'
import { sharedPointsState, type ScenePoint } from '../stores/sharedStore.ts';
import { getTabScopedId } from '../utils/clientId';
import RootSideProfile from './RootSideProfile.vue'
import TipSideProfile from './TipSideProfile.vue'

// 定义 CurveAssociation 接口
interface CurveAssociation {
  object: THREE.Object3D;
  meshes: THREE.Object3D[];
  labels: (THREE.Sprite | null)[];
  lines: THREE.Line[];
}
// 通过 defineProps 接收父组件传递的数据

// 新增：为旋转滑块添加一个 ref
const rollAngle = vueRef(0);
const isSceneReady = vueRef(false);
const props = defineProps<{
   sceneData: {
    backgroundImage: string,  // 图片 URL
    cameraRotation: number[],  // 相机旋转角度 (欧拉角)
    backgroundPlanePosition: { x: number, y: number, z: number } | null,
    imageScale?: number,  // 图片缩放比例
    AD_arc?: number
  },
  activeIndex?: number
}>()

// 内部活动索引（优先使用父组件传入的 activeIndex；保持为 null 则表示未知）
const activeIdxInternal = vueRef<number | null>(typeof props.activeIndex === 'number' ? props.activeIndex : null);
watch(() => props.activeIndex, (v) => {
  if (typeof v === 'number' && !Number.isNaN(v) && v >= 0) activeIdxInternal.value = v;
});

const zoomLevel = vueRef(1);
const imageScale = vueRef(1);

let bgOffsetFromCenter: THREE.Vector3 | null = null; // unused, kept for compat
// 定义一个按场景 key 存储偏移量的 Map
const sceneOffsetsMap = vueRef<Record<string, { r: number, u: number, f: number }>>({});

// 计算属性：获取当前场景的偏移量，如果没有则返回默认值
const currentOffsets = computed(() => {
  const key = currentSceneKey.value;
  // 如果 key 为 null 或者 map 中没有该场景，则返回默认初始位置（例如向前方 50 单位）
  if (!key || !sceneOffsetsMap.value[key]) {
    return { r: 0, u: 0, f: 50 }; 
  }
  return sceneOffsetsMap.value[key];
});


function handleRootPointUpdate(pointName: string, newPosition: THREE.Vector3) {
  const point = rootSidePoints.value.find(p => p.name === pointName)
  if (point) {
    point.x = newPosition.x
    point.y = newPosition.y
    point.z = newPosition.z

    if (pointName === 'A') {
      const sharedPositionPoint = sharedPointsState.positions.find(p => p.name === pointName)
      if (sharedPositionPoint) {
        sharedPositionPoint.x = newPosition.x
        sharedPositionPoint.y = newPosition.y
        sharedPositionPoint.z = newPosition.z
      }
    } else {
      const sharedPoint = sharedPointsState.sideProfilePoints.find(p => p.name === pointName)
      if (sharedPoint) {
        sharedPoint.x = newPosition.x
        sharedPoint.y = newPosition.y
        sharedPoint.z = newPosition.z
      }
    }

    regenerateNailModel()
  }
}

function handleTipPointUpdate(pointName: string, newPosition: THREE.Vector3) {
  const point = tipSidePoints.value.find(p => p.name === pointName)
  if (point) {
    point.x = newPosition.x
    point.y = newPosition.y
    point.z = newPosition.z

    if (pointName === 'D') {
      const leftControl = tipSidePoints.value.find(p => p.name === 'D_P1_J')
      const rightControl = tipSidePoints.value.find(p => p.name === 'D_P1_I')
      if (leftControl && rightControl) {
        const midpoint = new THREE.Vector3(
          (leftControl.x + rightControl.x) / 2,
          (leftControl.y + rightControl.y) / 2,
          (leftControl.z + rightControl.z) / 2,
        )
        point.x = midpoint.x
        point.y = midpoint.y
        point.z = midpoint.z
        newPosition = midpoint
      }
      const sharedPositionPoint = sharedPointsState.positions.find(p => p.name === pointName)
      if (sharedPositionPoint) {
        sharedPositionPoint.x = newPosition.x
        sharedPositionPoint.y = newPosition.y
        sharedPositionPoint.z = newPosition.z
      }
    } else {
      const sharedPoint = sharedPointsState.sideProfilePoints.find(p => p.name === pointName)
      if (sharedPoint) {
        sharedPoint.x = newPosition.x
        sharedPoint.y = newPosition.y
        sharedPoint.z = newPosition.z
      }
    }

    regenerateNailModel()
  }
}

function regenerateNailModel() {
  generateCustomBezierCurves(false)
}

function resetCameraToProps() {
  // 直接使用 props 中的原始 cameraRotation（可能是 3 元素 euler 或 4 元素 quaternion）
  const rotation = props.sceneData?.cameraRotation;
  if (rotation && (rotation.length === 3 || rotation.length === 4)) {
    applyCameraRotationFromArray(rotation);
    try {
      saveStateToLocalStorage();
      console.log('已重置到预设视角:', rotation);
    } catch (e) {}
  }
  // 将滑条归零
  try { pitchValue.value = 0; rollValue.value = 0; yawValue.value = 0; try { saveCameraDeltaForScene(currentSceneKey.value); } catch(e) {} } catch (e) {}
}

// 重置图片位置
function resetImagePosition() {
  if (!backgroundPlane || !camera) return;

  const cameraDirection = new THREE.Vector3();
  camera.getWorldDirection(cameraDirection);

  const planeDistance = 50;
  backgroundPlane.position.copy(dataCenter.value.clone().add(cameraDirection.clone().multiplyScalar(planeDistance)));
  backgroundPlane.quaternion.copy(camera.quaternion);

  recordCurrentOffsets();
  if (props.sceneData) {
    props.sceneData.backgroundPlanePosition = {
      x: backgroundPlane.position.x,
      y: backgroundPlane.position.y,
      z: backgroundPlane.position.z
    };
  }
  saveStateToLocalStorage();
  console.log('背景图片位置已复位');
}

// 记录当前背景图片相对于相机坐标系的偏移量到 sceneOffsetsMap
function recordCurrentOffsets() {
  if (!backgroundPlane || !camera) return;
  const key = currentSceneKey.value;
  if (!backgroundPlane || !camera || !key) return;
  // 1. 获取图片中心到 dataCenter 的向量
  const vec = new THREE.Vector3().subVectors(backgroundPlane.position, dataCenter.value);

  // 2. 获取相机当前的局部坐标轴方向（世界坐标系下）
  const cameraRight = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const cameraUp = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const cameraForward = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 2).negate();

  // 更新当前场景对应的偏移量
  sceneOffsetsMap.value[key] = {
    r: vec.dot(cameraRight),
    u: vec.dot(cameraUp),
    f: vec.dot(cameraForward)
  };
}

// 曲线名称列表
const curveNames = vueRef<string[]>(['AB', 'BC', 'CD', 'AF', 'FE', 'ED']);

// 新增：侧轮廓控制点数据
// 侧轮廓坐标系说明（对应 Python _expand_input_point 约定）：
//   sp.x = val1 = Python 归一化坐标系中的 Y 分量（指甲宽度方向，左负右正）
//   sp.y = val2 = Python 归一化坐标系中的 Z 分量（高度方向，负值=基平面以下）
//   ABCDEF 基础点 z=0（基平面），GHIJ 侧附着点 z<0（向下卷入手指侧边）
const rootSidePoints = vueRef<ScenePoint[]>([
  { name: 'G',     x: -3.0, y: -0.8, z: 0 }, // 左侧附着点（基平面以下，左侧）
  { name: 'H',     x:  3.2, y: -0.8, z: 0 }, // 右侧附着点（基平面以下，右侧）
  { name: 'A_P1_G', x: -2.0, y:  0.0, z: 0 }, // 左侧控制点（基平面处）
  { name: 'A_P1_H', x:  2.0, y:  0.0, z: 0 }, // 右侧控制点（基平面处）
  { name: 'A',     x:  0.0, y:  0.0, z: 0 }  // 中心基座点
])

const tipSidePoints = vueRef<ScenePoint[]>([
  { name: 'J',     x: -4.0, y: -1.2, z: 0 }, // 左侧附着点（基平面以下，左侧）
  { name: 'I',     x:  4.2, y: -1.2, z: 0 }, // 右侧附着点（基平面以下，右侧）
  { name: 'D_P1_J', x: -3.0, y:  0.0, z: 0 }, // 左侧控制点（基平面处）
  { name: 'D_P1_I', x:  3.0, y:  0.0, z: 0 }, // 右侧控制点（基平面处）
  { name: 'D',     x:  0.0, y:  0.0, z: 0 }  // 中心基座点
])

// 从 sharedPointsState 的 sideProfilePoints / positions 中同步 G/H/I/J 等侧轮廓点到 rootSidePoints/tipSidePoints
function syncSideProfilePointsFromStore() {
  const sideProfilePoints = sharedPointsState.sideProfilePoints || [];
  const positions = sharedPointsState.positions || [];
  const bezierPoints = sharedPointsState.bezierPoints || [];

  const findSidePoint = (name: string) => sideProfilePoints.find((p: any) => p.name === name);
  const findPositionPoint = (name: string) => positions.find((p: any) => p.name === name);
  const findBezierPoint = (name: string) => bezierPoints.find((p: any) => p.name === name);

  // 更新 rootSidePoints (G, A_P1_G, A, A_P1_H, H)
  for (const sp of rootSidePoints.value) {
    const found = sp.name === 'A'
      ? findPositionPoint('A')
      : findSidePoint(sp.name) ?? findBezierPoint(sp.name);
    if (found) {
      sp.x = found.x;
      sp.y = found.y;
      sp.z = found.z;
    }
  }

  const dPointFromModel = findPositionPoint('D') ?? findBezierPoint('D');
  const dLeftControl = findSidePoint('D_P1_J') ?? findBezierPoint('D_P1_J');
  const dRightControl = findSidePoint('D_P1_I') ?? findBezierPoint('D_P1_I');
  const derivedTipD = dLeftControl && dRightControl
    ? {
        x: (dLeftControl.x + dRightControl.x) / 2,
        y: (dLeftControl.y + dRightControl.y) / 2,
        z: (dLeftControl.z + dRightControl.z) / 2,
      }
    : null;

  // 更新 tipSidePoints (J, D_P1_J, D, D_P1_I, I)
  for (const sp of tipSidePoints.value) {
    const found = sp.name === 'D'
      ? derivedTipD ?? dPointFromModel
      : findSidePoint(sp.name) ?? findBezierPoint(sp.name);
    if (found) {
      sp.x = found.x;
      sp.y = found.y;
      sp.z = found.z;
    }
  }
}
syncSideProfilePointsFromStore();

// 监听 sideProfilePoints / positions / bezierPoints 变化，自动同步侧轮廓点
watch(() => sharedPointsState.sideProfilePoints, () => {
  syncSideProfilePointsFromStore();
}, { deep: true });
watch(() => sharedPointsState.positions, () => {
  syncSideProfilePointsFromStore();
}, { deep: true });
watch(() => sharedPointsState.bezierPoints, () => {
  syncSideProfilePointsFromStore();
}, { deep: true });

// 新增：参数控制
const xyRotationValue = vueRef(sharedPointsState.xyRotation || 0.0)
const aTangentValue = vueRef(sharedPointsState.aTangent || Math.PI / 10)

// 记录后端传来的原始参数值，用于重置按钮
let originalXyRotation: number = sharedPointsState.xyRotation || 0.0;
let originalATangent: number = sharedPointsState.aTangent || Math.PI / 10;
let isLocalParamChange = false; // 防止本地修改覆盖原始值

// 监听 sharedPointsState 中的 xyRotation 和 aTangent 变化
watch(() => sharedPointsState.xyRotation, (val) => {
  if (typeof val === 'number') {
    console.log('[ThreeScene] xyRotation updated from store:', val, '-> degrees:', val * 180 / Math.PI);
    xyRotationValue.value = val;
    if (!isLocalParamChange) {
      originalXyRotation = val; // 仅后端更新时记录原始值
    }
    isLocalParamChange = false;
    try { regenerateNailModel(); } catch(e) {}
  }
});
watch(() => sharedPointsState.aTangent, (val) => {
  if (typeof val === 'number') {
    console.log('[ThreeScene] aTangent updated from store:', val, '-> degrees:', val * 180 / Math.PI);
    aTangentValue.value = val;
    if (!isLocalParamChange) {
      originalATangent = val; // 仅后端更新时记录原始值
    }
    isLocalParamChange = false;
    try { regenerateNailModel(); } catch(e) {}
  }
});

const str_point = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
const containerRef = vueRef<HTMLElement | null>(null) // 使用 ref 引用容器
// 摄像机旋转滑条值（每个轴 1 个滑条）
const pitchValue = vueRef(0);
const rollValue = vueRef(0);
const yawValue = vueRef(0);

// 基准球坐标（用于根据相机朝向计算位置）
let baseSpherical: THREE.Spherical | null = null
// 存储后端提供的基准欧拉角（度），滑条作为对此的增量
const baseCameraEulerDeg = vueRef<[number, number, number]>([0, 0, 0]);

// 记录上次由后端/props 应用到相机的 cameraRotation（用于避免 props 中 cameraDelta 导致的回写覆盖）
let lastAppliedCameraRotation: number[] | null = null;

// 精度工具：获取数字的小数位数（尽量保留原始字符串表现）
function getDecimalPlaces(n: number): number {
  try {
    const s = String(n);
    if (s.indexOf('e') !== -1 || s.indexOf('E') !== -1) {
      // 科学计数法，尝试用较高精度格式化再判断
      const f = n.toFixed(6).replace(/0+$/, '');
      const idx = f.indexOf('.');
      return idx >= 0 ? (f.length - idx - 1) : 0;
    }
    const idx = s.indexOf('.')
    return idx >= 0 ? (s.length - idx - 1) : 0;
  } catch (e) { return 0; }
}

// 摄像机滑条显示/步长精度（以度为单位）
const cameraPrecision = vueRef<number>(1);
const cameraStep = computed(() => Math.pow(10, -Math.max(0, cameraPrecision.value)) );

// AD_arc 显示精度（度）
const adArcPrecision = vueRef<number>(1);
const adArcStep = computed(() => Math.pow(10, -Math.max(0, adArcPrecision.value)));

function updateCameraPrecisionFromProps() {
  try {
    const cr = props.sceneData?.cameraRotation;
    if (cr && Array.isArray(cr) && (cr.length === 3 || cr.length === 4)) {
      let x: number, y: number, z: number;
      if (cr.length === 4) {
        // 与实际显示链路保持一致：后端四元数先按协议重排/取逆，再转 Euler 用于精度显示
        const q = buildFrontendQuaternionFromRotation(cr).quaternion;
        const euler = new THREE.Euler().setFromQuaternion(q, 'XYZ');
        const toDeg = 180 / Math.PI;
        x = euler.x * toDeg;
        y = euler.y * toDeg;
        z = euler.z * toDeg;
      } else {
        x = cr[0];
        y = cr[1];
        z = cr[2];
      }
      const p = Math.max(getDecimalPlaces(x), getDecimalPlaces(y), getDecimalPlaces(z));
      cameraPrecision.value = p;
      return;
    }
    // Fallback to baseCameraEulerDeg if available
    if (baseCameraEulerDeg.value) {
      const p = Math.max(getDecimalPlaces(baseCameraEulerDeg.value[0]||0), getDecimalPlaces(baseCameraEulerDeg.value[1]||0), getDecimalPlaces(baseCameraEulerDeg.value[2]||0));
      cameraPrecision.value = p;
    }
  } catch (e) {}
}

// 监听 props 中的 cameraRotation 以同步精度
watch(() => props.sceneData && props.sceneData.cameraRotation, () => {
  updateCameraPrecisionFromProps();
}, { immediate: true });

// 新增：独立的背景同步函数
function syncBackgroundToCamera() {
  // 关键：如果正在拖拽背景，不要执行同步覆盖，否则拖不动
  // 同时检查 backgroundPlane 是否仍在 scene 中（parent !== null）
  if (!backgroundPlane || !camera || !backgroundPlane.parent || currentDragged === backgroundPlane) return;

  const { r, u, f } = currentOffsets.value;

  const cameraRight = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const cameraUp = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  const cameraForward = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 2).negate();

  // 基于当前场景的偏移量计算位置
  const newPos = dataCenter.value.clone()
    .add(cameraRight.multiplyScalar(r))
    .add(cameraUp.multiplyScalar(u))
    .add(cameraForward.multiplyScalar(f));

  backgroundPlane.position.copy(newPos);

  // 保持图片始终正对相机
  backgroundPlane.quaternion.copy(camera.quaternion);
  if (bgLocalQuat) {
    backgroundPlane.quaternion.multiply(bgLocalQuat);
  }
}

// 背景与摄像机的本地关系（相机固定后不再使用）
let bgLocalOffset: THREE.Vector3 | null = null;
let bgLocalQuat: THREE.Quaternion | null = null;
let currentDragged: THREE.Object3D | null = null;

// 滑条增量绕模型自身局部坐标轴应用，保持 pitch/yaw/roll 定义一致
function composeQuaternionFromBaseAndDeltas(
  baseQuaternion: THREE.Quaternion,
  pitchDeg: number,
  yawDeg: number,
  rollDeg: number,
): THREE.Quaternion {
  const pitchLocalQ = new THREE.Quaternion().setFromAxisAngle(
    new THREE.Vector3(1, 0, 0), THREE.MathUtils.degToRad(pitchDeg)
  );
  const yawLocalQ = new THREE.Quaternion().setFromAxisAngle(
    new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(yawDeg)
  );
  const rollLocalQ = new THREE.Quaternion().setFromAxisAngle(
    new THREE.Vector3(0, 0, 1), THREE.MathUtils.degToRad(rollDeg)
  );

  const localDelta = pitchLocalQ.clone().multiply(yawLocalQ).multiply(rollLocalQ);
  return baseQuaternion.clone().multiply(localDelta);
}

function convertBackendEulerToFrontendEulerDeg(rotation: number[]): [number, number, number] {
  const x_from_backend = Number(rotation[0]) || 0;
  const y_from_backend = Number(rotation[1]) || 0;
  const z_from_backend = Number(rotation[2]) || 0;

  return [
    -x_from_backend,
    -y_from_backend,
    90 - z_from_backend,
  ];
}

function quaternionToEulerDeg(quaternion: THREE.Quaternion): [number, number, number] {
  const euler = new THREE.Euler().setFromQuaternion(quaternion, 'XYZ');
  const toDeg = 180 / Math.PI;
  return [euler.x * toDeg, euler.y * toDeg, euler.z * toDeg];
}

function buildFrontendQuaternionFromRotation(rotation: number[]): {
  quaternion: THREE.Quaternion,
  baseEulerDeg: [number, number, number],
} {
  let quaternion: THREE.Quaternion;

  if (rotation.length === 4) {
    // 后端四元数按 [w, x, y, z] 传入；three.js 需要 [x, y, z, w]
    const qBackend = new THREE.Quaternion(
      Number(rotation[1]) || 0,
      Number(rotation[2]) || 0,
      Number(rotation[3]) || 0,
      Number(rotation[0]) || 1,
    ).normalize();

    // 后端字段虽然命名为 cameraRotation，但前端实际是把它作用到 modelGroup。
    // 为了在固定相机下复现相机姿态效果，这里取逆转成模型姿态。
    quaternion = qBackend.clone().invert();
  } else {
    const baseEulerDeg = convertBackendEulerToFrontendEulerDeg(rotation);
    quaternion = new THREE.Quaternion().setFromEuler(
      new THREE.Euler(
        THREE.MathUtils.degToRad(baseEulerDeg[0]),
        THREE.MathUtils.degToRad(baseEulerDeg[1]),
        THREE.MathUtils.degToRad(baseEulerDeg[2]),
        'XYZ'
      )
    );
  }

  return {
    quaternion,
    baseEulerDeg: quaternionToEulerDeg(quaternion),
  };
}

function getRotationMapFromStorage(): Record<string, number[]> {
  try {
    const raw = localStorage.getItem(ORIGINAL_ROTATION_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (e) {
    return {};
  }
}

function setRotationMapEntry(key: string, rotation: number[]) {
  try {
    const map = getRotationMapFromStorage();
    map[key] = rotation.slice();
    localStorage.setItem(ORIGINAL_ROTATION_KEY, JSON.stringify(map));
  } catch (e) {}
}

function getBaseEulerDegForRotation(rotation: number[] | null | undefined): [number, number, number] | null {
  if (!rotation || !Array.isArray(rotation) || rotation.length < 3) return null;
  try {
    return buildFrontendQuaternionFromRotation(rotation).baseEulerDeg;
  } catch (e) {
    return null;
  }
}

function getRotationForScene(key: string | null): number[] | null {
  const propsRotation = props.sceneData?.cameraRotation;
  if (propsRotation && Array.isArray(propsRotation) && (propsRotation.length === 3 || propsRotation.length === 4)) {
    return propsRotation.slice();
  }
  if (!key) return null;
  const arr = getRotationMapFromStorage()[key];
  if (Array.isArray(arr) && (arr.length === 3 || arr.length === 4)) {
    return arr.slice();
  }
  return null;
}

function clearStaleModelGroupQuaternion() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const state = JSON.parse(raw);
    if (state && typeof state === 'object' && 'modelGroupQuaternion' in state) {
      delete state.modelGroupQuaternion;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }
  } catch (e) {}
}

function clearLegacyRotationCache() {
  try {
    const map = getRotationMapFromStorage();
    let mutated = false;
    for (const key of Object.keys(map)) {
      const value = map[key];
      if (!Array.isArray(value) || (value.length !== 3 && value.length !== 4)) {
        delete map[key];
        mutated = true;
      }
    }
    if (mutated) {
      localStorage.setItem(ORIGINAL_ROTATION_KEY, JSON.stringify(map));
    }
  } catch (e) {}
}

function applySlidersToCamera() {
  if (!modelGroup) return;

  const rotation = getRotationForScene(currentSceneKey.value);
  const baseQuaternion = rotation
    ? buildFrontendQuaternionFromRotation(rotation).quaternion
    : new THREE.Quaternion().setFromEuler(new THREE.Euler(
        THREE.MathUtils.degToRad(baseCameraEulerDeg.value[0] || 0),
        THREE.MathUtils.degToRad(baseCameraEulerDeg.value[1] || 0),
        THREE.MathUtils.degToRad(baseCameraEulerDeg.value[2] || 0),
        'XYZ'
      ));
  const targetQuaternion = composeQuaternionFromBaseAndDeltas(
    baseQuaternion,
    pitchValue.value,
    yawValue.value,
    rollValue.value,
  );

  baseCameraEulerDeg.value = quaternionToEulerDeg(baseQuaternion);
  modelGroup.quaternion.copy(targetQuaternion);

  try { saveCameraDeltaForScene(currentSceneKey.value); } catch (e) {}
}

// 将后端/props 中的旋转数据应用到模型组
// 支持 3 元素欧拉角 [x,y,z]（度）和 4 元素四元数 [x,y,z,w]
function applyCameraRotationFromArray(newRotation: number[]) {
  if (!modelGroup) return;
  try {
    const { quaternion: targetQuaternion, baseEulerDeg } = buildFrontendQuaternionFromRotation(newRotation);
    baseCameraEulerDeg.value = baseEulerDeg;

    // 应用四元数到模型组
    modelGroup.quaternion.copy(targetQuaternion);

    // 保存真正的原始 rotation 到 localStorage（按场景映射）
    try {
      const key = getSceneKey();
      setRotationMapEntry(key, newRotation);
    } catch (e) {}

    // 计算模型旋转相对于标准坐标轴的轴角差并打印
    const q = targetQuaternion;
    const angle = 2 * Math.acos(Math.min(1, Math.abs(q.w)));
    const sinHalf = Math.sqrt(Math.max(0, 1 - q.w * q.w));
    const axis = new THREE.Vector3(q.x, q.y, q.z).divideScalar(sinHalf || 1);
    const angleDeg = angle * 180 / Math.PI;
    const sceneKey = currentSceneKey.value || getSceneKey();
    console.log(
      `[模型旋转轴角] 场景: ${sceneKey}\n` +
      `  后端原始: [${newRotation.join(', ')}]\n` +
      `  轴: (${axis.x.toFixed(4)}, ${axis.y.toFixed(4)}, ${axis.z.toFixed(4)})\n` +
      `  角: ${angleDeg.toFixed(2)}° (${angle.toFixed(6)} rad)\n` +
      `  四元数: (${q.x.toFixed(4)}, ${q.y.toFixed(4)}, ${q.z.toFixed(4)}, ${q.w.toFixed(4)})`
    );
  } catch (e) {
    console.warn('applyCameraRotationFromArray failed', e);
  }
  try { lastAppliedCameraRotation = newRotation.slice(); } catch (e) {}
}

// 保存当前相机状态（不回写 cameraRotation，避免覆盖原始 quaternion 触发循环）
function saveCurrentCameraRotationToProps() {
  if (camera && props.sceneData) {
    try {
      // 仅保存 cameraQuaternion 和 localStorage，不修改 props.sceneData.cameraRotation
      saveStateToLocalStorage();
    } catch (e) {
      console.warn('保存相机视角失败', e);
    }
  }
}
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer | undefined;
let modelGroup: THREE.Group;
const spheres: THREE.Mesh[] = []
const bezier_points: THREE.Mesh[] = []
// let curveObjects: THREE.Line[] = []
let curveObjects: THREE.Object3D[] = [];
// 曲线与关联点映射
let curveAssociations: CurveAssociation[] = [];
// 射线检测
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
raycaster.params.Line = { threshold: 0.1 };
let selectedAssociation: CurveAssociation | null = null;

// 顶层：选择/取消选择与点击逻辑（定义在模块级，供 onMounted/onUnmounted 使用）
function deselectAll() {
  selectedAssociation = null;
  for (let i = 0; i < bezier_points.length; i++) {
    if (bezier_points[i]) bezier_points[i].visible = false;
    if (bezierLabels[i]) bezierLabels[i].visible = false;
  }
  for (let i = 0; i < sphereLabels.length; i++) {
    if (sphereLabels[i]) sphereLabels[i].visible = false;
  }
  // 隐藏点与标签之间的连线
  for (const line of sphereLabelLines) {
    line.visible = false;
  }
  for (const line of bezierLabelLines) {
    line.visible = false;
  }
}

function selectAssociation(assoc: CurveAssociation) {
  deselectAll();
  selectedAssociation = assoc;
  for (let i = 0; i < assoc.meshes.length; i++) {
    const m = assoc.meshes[i];
    const bi = bezier_points.findIndex(b => b === m);
    if (bi !== -1) {
      bezier_points[bi].visible = true;
      if (bezierLabels[bi]) bezierLabels[bi].visible = true;
      // 显示点与标签之间的连线
      if (bezierLabelLines[bi]) bezierLabelLines[bi].visible = true;
      continue;
    }
    const si = spheres.findIndex(s => s === m);
    if (si !== -1) {
      if (sphereLabels[si]) sphereLabels[si].visible = true;
      // 显示点与标签之间的连线
      if (sphereLabelLines[si]) sphereLabelLines[si].visible = true;
    }
  }
}

function selectCurveByName(curveName: string) {
  const assoc = curveAssociations.find(a => {
    // 假设曲线名称可以通过某种方式关联，但实际上我们需要根据 meshes 的名称来判断
    // 例如，AB 对应 A 和 B 的 meshes
    // 但为了简单，我们可以根据 curveDefinitions 中的名称
    // 或者通过检查 meshes 的名称
    if (a.meshes.length >= 2) {
      const firstName = getPointName(a.meshes[0]);
      const lastName = getPointName(a.meshes[a.meshes.length - 1]);
      return firstName + lastName === curveName;
    }
    return false;
  });
  if (assoc) {
    selectAssociation(assoc);
  } else {
    deselectAll();
  }
}

// 辅助函数：从 mesh 获取点名称
function getPointName(mesh: THREE.Object3D): string {
  const sphereIndex = spheres.findIndex(s => s === mesh);
  if (sphereIndex !== -1) return sharedPointsState.positions[sphereIndex].name;
  const bezierIndex = bezier_points.findIndex(b => b === mesh);
  if (bezierIndex !== -1) return sharedPointsState.bezierPoints[bezierIndex].name;
  return '';
}

function onPointerDown(event: PointerEvent) {
  // 移除点击空白处隐藏的功能
}

// helper: get label sprite for a given mesh if exists (模块级)
function getLabelForMesh(mesh: THREE.Object3D): THREE.Sprite | null {
  const si = spheres.findIndex(s => s === mesh);
  if (si !== -1) return sphereLabels[si] || null;
  const bi = bezier_points.findIndex(b => b === mesh);
  if (bi !== -1) return bezierLabels[bi] || null;
  return null;
}
const bezierPointName = vueRef('')
// 用于存储3D文本标签
const sphereLabels: THREE.Sprite[] = [];
const bezierLabels: THREE.Sprite[] = [];
// 标签与球体之间的垂直偏移（可调，单位场景坐标）
const LABEL_VERTICAL_OFFSET = 7.0;
// 存储指示线（leader lines）
const sphereLabelLines: THREE.Line[] = [];
const bezierLabelLines: THREE.Line[] = [];
//  在顶层声明控制器变量，初始值为 undefined
let controls: OrbitControls | undefined;
let dragControls: DragControls | undefined;
const dragTargetPlane: THREE.Mesh | null = null;
let draggableObjects: THREE.Mesh[] = [];
let backgroundPlane: THREE.Mesh | null = null; // <-- 添加这一行
let lastLoadedBgImage: string = ''; // 记录上次加载的背景图片URL，避免重复重建
const bgCenter: THREE.Vector3 = new THREE.Vector3(); // 背景图片中心（独立于 dataCenter）
//let draggableImage: THREE.Mesh[] = []; // <-- 新增: 存储背景图片 Mesh

let geometry: THREE.SphereGeometry | undefined;
let material: THREE.MeshBasicMaterial | undefined;
let geometry_Bezier: THREE.SphereGeometry | undefined;
let material_Bezier: THREE.MeshBasicMaterial | undefined;


let animationFrameId: number | null = null; // <-- 添加这行声明
const isDragging = vueRef(false);

// AD_arc 控制（前端以度为单位显示/编辑，内部以弧度存储到 props.sceneData.AD_arc）
const defaultADArcRad = (1/5) * Math.PI;
const adArcDeg = vueRef(0);

function initAdArcFromProps() {
  const sceneKey = getSceneKey();
  // 读取并确保存在 original map 中的原始后端值（不受后续全局变更影响）
  try {
    const rawMap = localStorage.getItem(ORIGINAL_ADARC_MAP_KEY);
    let map: Record<string, number> = {};
    try { map = rawMap ? JSON.parse(rawMap) : {}; } catch (e) { map = {}; }
    if (typeof map[sceneKey] === 'number') {
      // original exists for this scene
    } else {
      const radFromProps = (props.sceneData && typeof props.sceneData.AD_arc === 'number') ? props.sceneData.AD_arc : defaultADArcRad;
      map[sceneKey] = radFromProps;
      try { localStorage.setItem(ORIGINAL_ADARC_MAP_KEY, JSON.stringify(map)); } catch (e) {}
    }
    const originalRad = map[sceneKey];

    // 优先使用共享 global（当前可被修改），否则读取 global localStorage 键，否则使用 original
    if (typeof (sharedPointsState as any).globalAdArc === 'number') {
      adArcDeg.value = (sharedPointsState as any).globalAdArc;
      // sync precision based on displayed degrees
      try { adArcPrecision.value = getDecimalPlaces(adArcDeg.value); } catch (e) {}
      return;
    }
    const rawGlobal = localStorage.getItem(GLOBAL_ADARC_KEY);
    if (rawGlobal) {
      const g = Number(rawGlobal);
      if (!Number.isNaN(g)) {
        sharedPointsState.globalAdArc = g;
        adArcDeg.value = g;
        try { adArcPrecision.value = getDecimalPlaces(adArcDeg.value); } catch (e) {}
        return;
      }
    }
    // 回退为 original，并把它设置为当前 global（但 original map 保持不变）
    sharedPointsState.globalAdArc = originalRad;
    try { localStorage.setItem(GLOBAL_ADARC_KEY, String(originalRad)); } catch (e) {}
    adArcDeg.value = originalRad;
    try { adArcPrecision.value = getDecimalPlaces(adArcDeg.value); } catch (e) {}
  } catch (e) {
    const rad = (props.sceneData && typeof props.sceneData.AD_arc === 'number') ? props.sceneData.AD_arc : defaultADArcRad;
    adArcDeg.value = rad;
    try { sharedPointsState.globalAdArc = rad; localStorage.setItem(GLOBAL_ADARC_KEY, String(rad)); adArcPrecision.value = getDecimalPlaces(adArcDeg.value); } catch (e) {}
  }
}

// 刷新所有球体/贝塞尔点的显示位置（应用当前 XY 旋转）
function refreshSphereDisplayPositions() {
  sharedPointsState.positions.forEach((pos, i) => {
    if (spheres[i]) {
      const dp = applyXYRotToPoint(Number(pos.x), Number(pos.y), Number(pos.z))
      spheres[i].position.copy(dp)
      if (sphereLabels[i]) {
        sphereLabels[i].position.copy(computeLabelPosition(spheres[i].position))
        const line = sphereLabelLines[i]
        if (line) {
          ;(line.geometry as THREE.BufferGeometry).setFromPoints([spheres[i].position.clone(), sphereLabels[i].position.clone()])
          line.geometry.attributes.position.needsUpdate = true
        }
      }
    }
  })
  sharedPointsState.bezierPoints.forEach((pos, i) => {
    if (bezier_points[i]) {
      const dp = applyXYRotToPoint(Number(pos.x), Number(pos.y), Number(pos.z))
      bezier_points[i].position.copy(dp)
      if (bezierLabels[i]) {
        bezierLabels[i].position.copy(computeLabelPosition(bezier_points[i].position))
        const bLine = bezierLabelLines[i]
        if (bLine) {
          ;(bLine.geometry as THREE.BufferGeometry).setFromPoints([bezier_points[i].position.clone(), bezierLabels[i].position.clone()])
          bLine.geometry.attributes.position.needsUpdate = true
        }
      }
    }
  })
}

function onParameterChange() {
  isLocalParamChange = true
  sharedPointsState.xyRotation = xyRotationValue.value
  isLocalParamChange = true
  sharedPointsState.aTangent = aTangentValue.value
  refreshSphereDisplayPositions()
  regenerateNailModel()
}

function resetXyRotation() {
  xyRotationValue.value = originalXyRotation
  onParameterChange()
}

function resetATangent() {
  aTangentValue.value = originalATangent
  onParameterChange()
}

function handleXyRotationInput(event: Event) {
  const target = event.target as HTMLInputElement
  const degrees = parseFloat(target.value)
  if (!isNaN(degrees)) {
    xyRotationValue.value = degrees * Math.PI / 180
    onParameterChange()
  }
}

function handleATangentInput(event: Event) {
  const target = event.target as HTMLInputElement
  const degrees = parseFloat(target.value)
  if (!isNaN(degrees)) {
    aTangentValue.value = degrees * Math.PI / 180
    onParameterChange()
  }
}

function handleATangentNumberInput(event: Event) {
  const target = event.target as HTMLInputElement
  const degrees = parseFloat(target.value)
  if (!isNaN(degrees)) {
    aTangentValue.value = degrees * Math.PI / 180
    onParameterChange()
  }
}

function onAdArcChange() {
  // 将度数转换为弧度并写回 props，先按显示精度舍入度数
  const roundedDeg = Number(adArcDeg.value);
  const rad = roundedDeg;
  try {
    // 更新共享全局 AD_arc（全局变动），并写入全局 localStorage 键
    sharedPointsState.globalAdArc = rad;
    try { localStorage.setItem(GLOBAL_ADARC_KEY, String(rad)); } catch (e) {}
  } catch (e) {}
  // 重新生成曲线
  try { generateCustomBezierCurves(false); } catch (e) {}
}

function resetAdArc() {
  // 从 original map 中读取该场景后端原始 AD_arc，并将 global 改为该值
  try {
    const sceneKey = getSceneKey();
    const rawMap = localStorage.getItem(ORIGINAL_ADARC_MAP_KEY);
    let map: Record<string, number> = {};
    try { map = rawMap ? JSON.parse(rawMap) : {}; } catch (e) { map = {}; }
    const original = (typeof map[sceneKey] === 'number') ? map[sceneKey] : ((props.sceneData && typeof props.sceneData.AD_arc === 'number') ? props.sceneData.AD_arc : defaultADArcRad);
    // set global to original
    sharedPointsState.globalAdArc = original;
    try { localStorage.setItem(GLOBAL_ADARC_KEY, String(original)); } catch (e) {}
    adArcDeg.value = original;
    try { generateCustomBezierCurves(false); } catch (e) {}
  } catch (e) {
    // fallback
    initAdArcFromProps();
    try { generateCustomBezierCurves(false); } catch (e) {}
  }
}

// 当 props.sceneData.AD_arc 变化或组件挂载时初始化 adArcDeg
watch(() => props.sceneData && (props.sceneData.AD_arc ?? null), () => {
  initAdArcFromProps();
}, { immediate: true });

// 初始化或恢复每个场景的滑条增量（独立于其它场景）
// 我们会在场景切换前保存当前场景的 delta 到 localStorage 映射，并在新场景加载时恢复
const currentSceneKey = vueRef<string | null>(null);

function loadCameraDeltaForScene(key: string | null) {
  if (!key) return;
  try {
    const raw = localStorage.getItem(CAMERA_DELTA_MAP_KEY);
    const map = raw ? JSON.parse(raw) : {};
    const entry = map[key];
    if (entry && typeof entry.pitchDelta === 'number') pitchValue.value = entry.pitchDelta; else pitchValue.value = 0;
    if (entry && typeof entry.rollDelta === 'number') rollValue.value = entry.rollDelta; else rollValue.value = 0;
    if (entry && typeof entry.yawDelta === 'number') yawValue.value = entry.yawDelta; else yawValue.value = 0;
    // 不写入 props.sceneData.cameraDelta，避免触发深层 watcher 级联
  } catch (e) {
    try {
      const d = (props.sceneData as any)?.cameraDelta;
      if (d && typeof d.pitchDelta === 'number') pitchValue.value = d.pitchDelta; else pitchValue.value = 0;
      if (d && typeof d.rollDelta === 'number') rollValue.value = d.rollDelta; else rollValue.value = 0;
      if (d && typeof d.yawDelta === 'number') yawValue.value = d.yawDelta; else yawValue.value = 0;
    } catch (e) {}
  }
}

// 读取原始后端视角（如果存在）
function getOriginalRotationForScene(key: string | null): number[] | null {
  if (!key) return null;
  try {
    const raw = localStorage.getItem(ORIGINAL_ROTATION_KEY);
    if (!raw) {
      const arr = props.sceneData && Array.isArray(props.sceneData.cameraRotation) ? props.sceneData.cameraRotation : null;
      return arr;
    }
    else {
      const map = JSON.parse(raw);
      const arr = map && Array.isArray(map[key]) ? map[key] : null;
      return arr;
    }
    
  } catch (e) {
    return null;
  }
}

// 将原始后端 rotation 加载为前端 baseCameraEulerDeg（度）
// 支持 3 元素欧拉角和 4 元素四元数（优先 props，其次 localStorage 原始映射）
function loadOriginalBaseForScene(key: string | null) {
  try {
    const rotation = getRotationForScene(key);
    const baseEuler = getBaseEulerDegForRotation(rotation);
    if (baseEuler) {
      baseCameraEulerDeg.value = baseEuler;
      try {
        cameraPrecision.value = Math.max(
          getDecimalPlaces(baseEuler[0]),
          getDecimalPlaces(baseEuler[1]),
          getDecimalPlaces(baseEuler[2]),
        );
      } catch (e) {}
    } else {
      try { updateCameraPrecisionFromProps(); } catch (e) {}
    }
  } catch (e) {}
}

function saveCameraDeltaForScene(key: string | null) {
  if (!key) return;
  try {
    const raw = localStorage.getItem(CAMERA_DELTA_MAP_KEY);
    let map: Record<string, any> = {};
    try { map = raw ? JSON.parse(raw) : {}; } catch (e) { map = {}; }
    map[key] = { pitchDelta: pitchValue.value, rollDelta: rollValue.value, yawDelta: yawValue.value };
    try { localStorage.setItem(CAMERA_DELTA_MAP_KEY, JSON.stringify(map)); } catch (e) {}
    // 不写入 props.sceneData.cameraDelta，避免触发深层 watcher 导致闪烁
  } catch (e) {}
}

  // 卸载时保存当前场景的 camera delta
  try { saveCameraDeltaForScene(currentSceneKey.value); } catch (e) {}

watch(() => props.sceneData, (newVal, oldVal) => {
  try {
    // 保存旧场景
    const prevKey = currentSceneKey.value;
    if (prevKey) saveCameraDeltaForScene(prevKey);
  } catch (e) {}
  // 计算新场景 key 并加载
  const newKey = getSceneKey();
  currentSceneKey.value = newKey;
  loadCameraDeltaForScene(newKey);
  // 加载并设置原始后端角度作为 base
  try { loadOriginalBaseForScene(newKey); } catch (e) {}

  // 场景切换后立即按“当前场景原始 rotation + 当前场景独立 delta”重算显示姿态，
  // 避免在下一次渲染或用户拖动滑条前，暂时沿用上一个场景的 modelGroup.quaternion。
  try {
    const rotation = getRotationForScene(newKey);
    if (rotation && modelGroup) {
      applyCameraRotationFromArray(rotation);
      if (pitchValue.value !== 0 || rollValue.value !== 0 || yawValue.value !== 0) {
        applySlidersToCamera();
      }
    }
  } catch (e) {}
}, { immediate: true });

// 监听共享全局 AD_arc 的变化，以便在多个场景中同步应用
watch(() => (sharedPointsState as any).globalAdArc, () => {
  try {
    if (typeof (sharedPointsState as any).globalAdArc === 'number') {
      adArcDeg.value = (sharedPointsState as any).globalAdArc;
      // 重新绘制当前场景的曲线
      try { generateCustomBezierCurves(false); } catch (e) {}
    }
  } catch (e) {}
});

// 控制是否允许拖动背景图片（默认为 false，需要用户点击开关）
const allowBackgroundDrag = vueRef(false);

function setBackgroundDraggable(enabled: boolean) {
  if (!backgroundPlane || !backgroundPlane.parent) return;
  const hasInList = draggableObjects.includes(backgroundPlane);
  if (enabled && !hasInList) {
    draggableObjects.push(backgroundPlane);
  } else if (!enabled && hasInList) {
    draggableObjects = draggableObjects.filter(obj => obj !== backgroundPlane);
  }
  if (dragControls) dragControls.objects = draggableObjects;
}

// 当用户切换 allowBackgroundDrag 时，更新 draggableObjects
watch(allowBackgroundDrag, (val) => setBackgroundDraggable(val));

// 当 imageScale 改变时，更新 backgroundPlane 的缩放
watch(imageScale, (val) => {
  if (backgroundPlane) {
    backgroundPlane.scale.set(val, val, 1);
  }
  // 更新场景数据
  if (props.sceneData) {
    props.sceneData.imageScale = val;
  }
});

// 历史记录栈（记录球体与贝塞尔点 positions）
type Snapshot = {
  spheres: Array<{x:number,y:number,z:number}>;
  beziers: Array<{x:number,y:number,z:number}>;
}

const undoStack = vueRef<Snapshot[]>([]);
const redoStack = vueRef<Snapshot[]>([]);

const canUndo = computed(() => undoStack.value.length > 0);
const canRedo = computed(() => redoStack.value.length > 0);

function snapshotPositions(): Snapshot {
  return {
    spheres: sharedPointsState.positions.map(p => ({ x: Number(p.x), y: Number(p.y), z: Number(p.z) })),
    beziers: sharedPointsState.bezierPoints.map(p => ({ x: Number(p.x), y: Number(p.y), z: Number(p.z) })),
  };
}

function applyPositions(state: Snapshot) {
  // spheres
  for (let i = 0; i < state.spheres.length; i++) {
    const s = state.spheres[i];
    if (sharedPointsState.positions[i]) {
      sharedPointsState.positions[i].x = s.x;
      sharedPointsState.positions[i].y = s.y;
      sharedPointsState.positions[i].z = s.z;
    }
    if (spheres[i]) {
      spheres[i].position.set(s.x, s.y, s.z);
    }
    if (sphereLabels[i]) {
      sphereLabels[i].position.copy(computeLabelPosition(spheres[i].position));
    }
    if (sphereLabelLines[i]) {
      (sphereLabelLines[i].geometry as THREE.BufferGeometry).setFromPoints([spheres[i].position.clone(), sphereLabels[i].position.clone()]);
      sphereLabelLines[i].geometry.attributes.position.needsUpdate = true;
    }
  }

  // beziers
  for (let i = 0; i < state.beziers.length; i++) {
    const b = state.beziers[i];
    if (sharedPointsState.bezierPoints[i]) {
      sharedPointsState.bezierPoints[i].x = b.x;
      sharedPointsState.bezierPoints[i].y = b.y;
      sharedPointsState.bezierPoints[i].z = b.z;
    }
    if (bezier_points[i]) {
      bezier_points[i].position.set(b.x, b.y, b.z);
    }
    if (bezierLabels[i]) {
      bezierLabels[i].position.copy(computeLabelPosition(bezier_points[i].position));
    }
    if (bezierLabelLines[i]) {
      (bezierLabelLines[i].geometry as THREE.BufferGeometry).setFromPoints([bezier_points[i].position.clone(), bezierLabels[i].position.clone()]);
      bezierLabelLines[i].geometry.attributes.position.needsUpdate = true;
    }
  }
  // 重新生成依赖点位置的贝塞尔/曲线
  generateCustomBezierCurves();
}

function pushUndoSnapshot() {
  undoStack.value.push(snapshotPositions());
  // 清空 redo
  redoStack.value.length = 0;
}

function undo() {
  if (undoStack.value.length === 0) return;
  const current = snapshotPositions();
  const prev = undoStack.value.pop()!;
  redoStack.value.push(current);
  applyPositions(prev);
}

function redo() {
  if (redoStack.value.length === 0) return;
  const current = snapshotPositions();
  const next = redoStack.value.pop()!;
  undoStack.value.push(current);
  applyPositions(next);
}


const firstCentered = vueRef(false); // 用于确保只居中一次
const dataCenter = vueRef<THREE.Vector3>(new THREE.Vector3()); // 每个组件实例独立的 dataCenter

// Local storage key（加 tabScope 后缀实现标签页隔离）
const tabScope = getTabScopedId();
const STORAGE_KEY = `frame_build_three_scene_state_v1_${tabScope}`;
// 存储后端原始视角的独立键（按场景存储为映射）
const ORIGINAL_ROTATION_KEY = STORAGE_KEY + '_original_camera_rotation_map';
// 全局存储 AD_arc 的键（统一在所有场景中同步）
const GLOBAL_ADARC_KEY = STORAGE_KEY + '_global_adarc';
// 存储后端原始 AD_arc 的映射（按场景 key 存储原始值，reset 读取它）
const ORIGINAL_ADARC_MAP_KEY = STORAGE_KEY + '_original_adarc_map';
// 存储每个场景的滑条增量映射（按场景 key 存储）
const CAMERA_DELTA_MAP_KEY = STORAGE_KEY + '_camera_delta_map';

// 生成当前场景的唯一键（优先使用背景图片 URL，回退到字符串 'default_scene'）
function getSceneKey(): string {
  try {
    if (props && props.sceneData && typeof props.sceneData.backgroundImage === 'string' && props.sceneData.backgroundImage.length > 0) {
      return props.sceneData.backgroundImage;
    }
  } catch (e) { /* ignore */ }
  return 'default_scene';
}

function saveStateToLocalStorage() {
  try {
    const state: any = {
      positions: sharedPointsState.positions,
      bezierPoints: sharedPointsState.bezierPoints,
      backgroundImage: props.sceneData?.backgroundImage ?? null,
      backgroundPlanePosition: backgroundPlane ? { x: backgroundPlane.position.x, y: backgroundPlane.position.y, z: backgroundPlane.position.z } : (props.sceneData?.backgroundPlanePosition ?? null),
      cameraRotation: props.sceneData?.cameraRotation ?? null,
      zoomLevel: zoomLevel.value,
      rollAngle: rollAngle.value,
      imageScale: imageScale.value,
      dataCenter: { x: dataCenter.value.x, y: dataCenter.value.y, z: dataCenter.value.z },
      allowBackgroundDrag: allowBackgroundDrag.value,
      undoStack: undoStack.value,
      redoStack: redoStack.value
    };
    // 不再持久化全局 modelGroupQuaternion，避免不同场景之间串用姿态基准
    // 合并已存在的 persisted scenes（仅保留 metadata，不把 shared 点写入到单独场景中）
    try {
      const existingRaw = localStorage.getItem(STORAGE_KEY);
      if (existingRaw) {
        const existing = JSON.parse(existingRaw);
        if (existing && Array.isArray(existing.scenes)) {
          // 保留已有的 scenes 元数据（不注入 positions/bezierPoints 到 scenes[*]）
          state.scenes = existing.scenes;
        }
      }
      // 如果本地没有 scenes，但 props 提供了当前场景的 metadata，则初始化 scenes 为单元素数组（仅 metadata）
      if (!state.scenes && props.sceneData) {
        state.scenes = [{ backgroundImage: props.sceneData.backgroundImage, cameraRotation: props.sceneData.cameraRotation, backgroundPlanePosition: props.sceneData.backgroundPlanePosition ?? null }];
      }
    } catch (e) {
      // 忽略解析错误，继续保存当前 state
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    // console.log('Saved scene state to localStorage.');
  } catch (e) {
    console.error('Failed to save scene state', e);
  }
}

function loadStateFromLocalStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    if (!state) return null;
    // restore positions and beziers (replace arrays)
    if (Array.isArray(state.positions)) {
      // clear and push
      sharedPointsState.positions.splice(0, sharedPointsState.positions.length, ...state.positions.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) })) );
    }
    if (Array.isArray(state.bezierPoints)) {
      sharedPointsState.bezierPoints.splice(0, sharedPointsState.bezierPoints.length, ...state.bezierPoints.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) })) );
    }
    // Do NOT overwrite props.sceneData (backgroundImage/cameraRotation/etc.) here.
    // The parent (`SidePanel`) controls which scene metadata is passed into this component.
    if (typeof state.zoomLevel === 'number') zoomLevel.value = state.zoomLevel;
    if (typeof state.rollAngle === 'number') rollAngle.value = state.rollAngle;
    if (typeof state.imageScale === 'number') imageScale.value = state.imageScale;
    if (state.dataCenter) dataCenter.value.set(Number(state.dataCenter.x)||0, Number(state.dataCenter.y)||0, Number(state.dataCenter.z)||0);
    // 恢复 allowBackgroundDrag
    if (typeof state.allowBackgroundDrag === 'boolean') {
      allowBackgroundDrag.value = state.allowBackgroundDrag;
    }
    // 恢复 undo/redo 栈
    if (Array.isArray(state.undoStack)) {
      try { undoStack.value = state.undoStack as Snapshot[]; } catch(e) { undoStack.value = []; }
    }
    if (Array.isArray(state.redoStack)) {
      try { redoStack.value = state.redoStack as Snapshot[]; } catch(e) { redoStack.value = []; }
    }
    return state;
  } catch (e) {
    console.error('Failed to load scene state', e);
    return null;
  }
}

// 点云数据存储
const allMeshPointsForExport = vueRef<THREE.Vector3[]>([]);
// 创建3D文本标签的辅助函数
function makeTextSprite(message: string, opts: { fontsize: number, fontface: string, textColor: {r:number, g:number, b:number, a:number} }) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) return new THREE.Sprite();

    // 1. 提高基础字号以获得更高清晰度 (类似高清屏逻辑)
    const displayFontSize = opts.fontsize * 2; 
    context.font = `Bold ${displayFontSize}px ${opts.fontface}`;
    
    // 2. 精确测量文本
    const metrics = context.measureText(message);
    const textWidth = metrics.width;
    
    // 动态调整画布，增加适度留白
    canvas.width = textWidth + 40; 
    canvas.height = displayFontSize + 40;
    
    // 3. 绘制文字
    context.font = `Bold ${displayFontSize}px ${opts.fontface}`;
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    
    // 添加文字阴影/描边，让文字在复杂背景下更清晰
    context.strokeStyle = 'rgba(0,0,0,0.8)';
    context.lineWidth = 4;
    context.strokeText(message, canvas.width / 2, canvas.height / 2);

    context.fillStyle = `rgba(${opts.textColor.r}, ${opts.textColor.g}, ${opts.textColor.b}, ${opts.textColor.a})`;
    context.fillText(message, canvas.width / 2, canvas.height / 2);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    
    const spriteMaterial = new THREE.SpriteMaterial({ 
        map: texture, 
        transparent: true, 
        depthTest: false, 
        depthWrite: false 
    });
    
    const sprite = new THREE.Sprite(spriteMaterial);
    sprite.renderOrder = 9999;

    // 4. 【关键修复】根据 Canvas 的实际宽高比进行缩放
    const aspect = canvas.width / canvas.height;
    const baseHeight = opts.fontsize / 8; // 这个系数决定了标签在 3D 空间的大小
    sprite.scale.set(baseHeight * aspect, baseHeight, 1.0);
    
    return sprite;
}

// 计算标签位置：从数据中心指向物体方向偏移 LABEL_VERTICAL_OFFSET
function computeLabelPosition(origin: THREE.Vector3, name: string = ''): THREE.Vector3 {
  // 1. 计算方向（保持原有逻辑，从中心向外辐射）
  const dir = origin.clone().sub(dataCenter.value);
  
  // 防止中心点重合
  if (dir.lengthSq() < 1e-8) {
    dir.set(0, 1, 0); 
  } else {
    dir.normalize();
  }

  // 2. 核心修改：动态长度
  // 默认高度
  let offsetDistance = 6; 

  // 如果名字包含下划线（如 AB_P1），通常是密集控制点，让引线短一点
  if (name.includes('_')) {
    // 甚至可以根据 P1, P2 进一步错开
    if (name.includes('P1') || name.includes('P3')) {
       offsetDistance = 6; // 第一层
    } else {
       offsetDistance = 6; // 第二层
    }
  } else {
    // 主点 A, B, C... 设得更高，作为第三层
    offsetDistance = 6.0; 
  }

  return origin.clone().add(dir.multiplyScalar(offsetDistance));
}

// 标签位置疏松算法
const RELAX_ITERATIONS = 4; // 每帧计算次数，越高越稳但耗能
const MIN_DISTANCE = 10.0;   // 标签之间的最小舒适距离
const PULL_STRENGTH = 0.01; // 拉回原位置的力（像弹簧一样连着球）
const PUSH_STRENGTH = 0.3;  // 标签之间的斥力

function relaxLabels() {
  // 1. 收集所有当前可见的标签对象
  // 结构：{ labelSprite, anchorPoint(球的位置), idealPosition(理想位置) }
  const activeLabels: { 
    sprite: THREE.Sprite, 
    anchor: THREE.Vector3, 
    ideal: THREE.Vector3,
    line: THREE.Line 
  }[] = [];

  // 收集球体标签
  sphereLabels.forEach((label, i) => {
    if (label.visible && spheres[i]) {
      // 重新计算理想位置（这里假设已经应用了方案一的分层逻辑，如果没有，offset传7.0即可）
      const name = sharedPointsState.positions[i]?.name || '';
      const ideal = computeLabelPosition(spheres[i].position, name);
      activeLabels.push({ 
        sprite: label, 
        anchor: spheres[i].position, 
        ideal: ideal,
        line: sphereLabelLines[i]
      });
    }
  });

  // 收集贝塞尔点标签
  bezierLabels.forEach((label, i) => {
    if (label.visible && bezier_points[i]) {
      const name = sharedPointsState.bezierPoints[i]?.name || '';
      const ideal = computeLabelPosition(bezier_points[i].position, name);
      activeLabels.push({ 
        sprite: label, 
        anchor: bezier_points[i].position, 
        ideal: ideal,
        line: bezierLabelLines[i]
      });
    }
  });

  // 2. 迭代计算位置（简单的力导向布局）
  for (let iter = 0; iter < RELAX_ITERATIONS; iter++) {
    for (let i = 0; i < activeLabels.length; i++) {
      const itemA = activeLabels[i];
      const posA = itemA.sprite.position;

      // 力 1: 吸引力 (尝试回到 computeLabelPosition 计算出的理想位置)
      // 向量：理想位置 - 当前位置
      const pullForce = itemA.ideal.clone().sub(posA).multiplyScalar(PULL_STRENGTH);
      posA.add(pullForce);

      // 力 2: 斥力 (被其他标签推开)
      for (let j = 0; j < activeLabels.length; j++) {
        if (i === j) continue;
        const itemB = activeLabels[j];
        const posB = itemB.sprite.position;

        const diff = posA.clone().sub(posB);
        const distSq = diff.lengthSq();
        
        // 如果距离小于阈值，产生斥力
        if (distSq < MIN_DISTANCE * MIN_DISTANCE) {
          const dist = Math.sqrt(distSq);
          // 距离越近，斥力越大；防止除以0
          const forceMagnitude = (dist > 0.01) ? (MIN_DISTANCE - dist) / dist : 1.0; 
          const pushVector = diff.normalize().multiplyScalar(forceMagnitude * PUSH_STRENGTH);
          
          // A 被推开，B 反向推开 (可选，这里简化只动A)
          posA.add(pushVector);
        }
      }
    }
  }

  // 3. 更新连线 (Leader Lines)
  // 因为标签位置变了，线也要跟着变
  activeLabels.forEach(item => {
    if (item.line) {
      const positions = item.line.geometry.attributes.position.array as Float32Array;
      // 起点：球的位置
      positions[0] = item.anchor.x;
      positions[1] = item.anchor.y;
      positions[2] = item.anchor.z;
      // 终点：标签的新位置
      positions[3] = item.sprite.position.x;
      positions[4] = item.sprite.position.y;
      positions[5] = item.sprite.position.z;
      item.line.geometry.attributes.position.needsUpdate = true;
    }
  });
}


// 添加球体
function addSphere() {
  const used =  sharedPointsState.positions.map(p => p.name)
  const next = str_point.split('').find(l => !used.includes(l))
  if (next) {
     sharedPointsState.positions.push({ name: next, x: 0, y: 0, z: 0 })
  }
}

// 删除球体
function removeSphere(idx: number) {
  if ( sharedPointsState.positions.length > 1) {
     sharedPointsState.positions.splice(idx, 1)
  }
}

// 添加贝塞尔曲线控制点
function addBezierPoint(name: string) {
  if (name) {
     sharedPointsState.bezierPoints
.push({ name, x: 0, y: 0, z: 0 })
    bezierPointName.value = '' // 清空输入框
  }
}

// 删除贝塞尔曲线控制点
function removeBezierPoint(idx: number) {
  if ( sharedPointsState.bezierPoints
.length > 0) {
     sharedPointsState.bezierPoints
.splice(idx, 1)
  }
}

// 辅助函数：将角度转换为弧度
function degToRad(degrees: number): number {
    return degrees * (Math.PI / 180);
}

// 将单个点按当前 xyRotation 旋转后返回显示位置
function applyXYRotToPoint(x: number, y: number, z: number): THREE.Vector3 {
    const angle = xyRotationValue.value;
    if (Math.abs(angle) < 1e-12) return new THREE.Vector3(x, y, z);
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), -angle);
    return new THREE.Vector3(x, y, z).applyQuaternion(q);
}

// 将单个 THREE.Vector3（显示坐标）逆旋转回原始数据坐标
function applyXYRotInverse(v: THREE.Vector3): THREE.Vector3 {
    const angle = xyRotationValue.value;
    if (Math.abs(angle) < 1e-12) return v.clone();
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), angle); // 反向
    return v.clone().applyQuaternion(q);
}

// 辅助函数：旋转向量 (对应 _rotate_vector)
function rotateVector(vectorOrigin: THREE.Vector3, planeVector: THREE.Vector3, theta: number): THREE.Vector3 {
    // Three.js 的旋转是基于四元数的
    const rotationQuaternion = new THREE.Quaternion().setFromAxisAngle(planeVector.normalize(), -theta);
    const newVector = vectorOrigin.clone().applyQuaternion(rotationQuaternion);
    return newVector;
}

// 辅助函数：绕轴旋转点集 (对应 _rotate_points_around_axis)
function rotatePointsAroundAxis(points: THREE.Vector3[], axisCenter: THREE.Vector3, axisNormal: THREE.Vector3, theta: number): THREE.Vector3[] {
    const rotatedPoints: THREE.Vector3[] = [];
    const rotationQuaternion = new THREE.Quaternion().setFromAxisAngle(axisNormal.normalize(), theta);

    for (const p of points) {
        const translatedPoint = p.clone().sub(axisCenter);
        const rotatedPoint = translatedPoint.applyQuaternion(rotationQuaternion);
        const finalPoint = rotatedPoint.add(axisCenter);
        rotatedPoints.push(finalPoint);
    }
    return rotatedPoints;
}

// 辅助函数：计算线与平面的交点 (对应 _line_intersection_with_AD_plane)
function lineIntersectionWithADPlane(A: THREE.Vector3, D: THREE.Vector3, P1: THREE.Vector3, P2: THREE.Vector3): THREE.Vector3 | null {
    // 平面方程: ax + by = c (z-axis vertical plane)
    const a = D.y - A.y;
    const b = A.x - D.x;
    const c = a * A.x + b * A.y;

    // Line equation: P(t) = P1 + t * (P2 - P1)
    const lineDirection = P2.clone().sub(P1);
    const denominator = a * lineDirection.x + b * lineDirection.y;
    const numerator = c - (a * P1.x + b * P1.y);

    if (Math.abs(denominator) < 1e-9) {
        return null; // 平行或共面
    }

    const t = numerator / denominator;
    const intersectionPoint : THREE.Vector3 = new THREE.Vector3();//P1.clone().add(lineDirection.multiplyScalar(t));
    const x = P1.x + t * (P2.x - P1.x);
    intersectionPoint.x = x;
    const y = P1.y + t * (P2.y - P1.y);
    intersectionPoint.y = y;
    const z = P1.z + t * (P2.z - P1.z);
    intersectionPoint.z = z;

    return intersectionPoint;
}

// 辅助函数：绕轴旋转圆弧生成曲面（_construct_surface_from_rotated_arc）
function constructSurfaceFromRotatedArc(arcPoints: THREE.Vector3[], axisCenter: THREE.Vector3, axisNormal: THREE.Vector3, direction: number): THREE.Vector3[] {
    const torusPoints: THREE.Vector3[] = [];
    const numRotations = 50;
    const totalAngle = Math.PI / 6 * direction; // 对应于 py 中的 np.pi/6

    for (let i = 0; i < numRotations; i++) {
        const theta = (i / (numRotations - 1)) * totalAngle;
        const rotatedPoints = rotatePointsAroundAxis(arcPoints, axisCenter, axisNormal, theta);
        torusPoints.push(...rotatedPoints);
    }
    return torusPoints;
}

// 辅助函数：正则化边缘 Z 坐标（_regularize_edge_z）
function regularizeEdgeZ(surfacePoints: THREE.Vector3[], bezierPoints: THREE.Vector3[]): THREE.Vector3[] {
    const regularizedPoints: THREE.Vector3[] = [];
    
    for (const bPoint of bezierPoints) {
        let closestZ = bPoint.z;
        let minDistanceSq = Infinity;

        for (const sPoint of surfacePoints) {
            const dx = bPoint.x - sPoint.x;
            const dy = bPoint.y - sPoint.y;
            const distanceSq = dx * dx + dy * dy;
            if (distanceSq < minDistanceSq) {
                minDistanceSq = distanceSq;
                closestZ = sPoint.z;
            }
        }
        
        regularizedPoints.push(new THREE.Vector3(bPoint.x, bPoint.y, closestZ));
    }
    return regularizedPoints;
}

/**
 * 使用射线投射算法 (Ray Casting Algorithm) 检查一个点是否在多边形内部。
 * 这是 `shapely.polygon.contains()` 的 JavaScript 实现。
 * @param point 要检查的点 {x, y}
 * @param polygon 构成多边形的顶点数组 [{x, y}, ...]
 * @returns 如果点在多边形内部，则返回 true
 */
function isPointInPolygon(point: { x: number, y: number }, polygon: { x: number, y: number }[]): boolean {
    const x = point.x;
    const y = point.y;
    let isInside = false;

    // 遍历多边形的每一条边
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const xi = polygon[i].x, yi = polygon[i].y;
        const xj = polygon[j].x, yj = polygon[j].y;

        // 检查从点发出的水平射线是否与当前边相交
        //   边的两个端点必须在射线的两侧 (一个y大于点y，一个y小于点y)
        //  交点的x坐标必须在点的右侧
        const intersect = ((yi > y) !== (yj > y))
            && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
        
        if (intersect) {
            // 每穿过一条边，内外状态反转一次
            isInside = !isInside;
        }
    }

    return isInside;
}

// 辅助函数：根据轮廓裁剪曲面（_cut_end_surface）
function cutEndSurface(surfacePoints: THREE.Vector3[], bezierPoints: THREE.Vector3[]): THREE.Vector3[] {
     // 轮廓至少需要3个点才能构成一个有效的多边形
    if (bezierPoints.length < 3) {
        console.warn("用于裁剪的轮廓点必须至少有3个。");
        return [];
    }

    // 为了优化性能，我们只进行一次从 Vector3[]到 {x, y}[] 的转换
    const contour2D = bezierPoints.map(p => ({ x: p.x, y: p.y }));

    // 使用 filter 方法，保留所有在轮廓内部的点
    return surfacePoints.filter(point3D => {
        // 将3D点投影到2D平面
        const point2D = { x: point3D.x, y: point3D.y };
        // 调用辅助函数进行精确判断
        return isPointInPolygon(point2D, contour2D);
    });
}

function getCircle3d(p1: Vector3, p2: Vector3, p3: Vector3): { center: Vector3, radius: number } | null {
     //   将输入点转换为 THREE.Vector3 以进行向量运算
    const v1 = p1.clone();
    const v2 = p2.clone();
    const v3 = p3.clone();

    //  计算定义平面的向量
    const v12 = v2.clone().sub(v1); // v2 - v1
    const v13 = v3.clone().sub(v1); // v3 - v1

    //   检查三点是否共线
    // 如果两个向量的叉积为零向量，则说明它们平行，三点共线
    const planeNormal = v12.clone().cross(v13);
    if (planeNormal.lengthSq() < 1e-8) {
        console.warn("getCircle3d: Three points are collinear, cannot determine a unique circle.");
        return null;
    }

    //   建立线性方程组 Ax = b 来求解圆心
    // A 矩阵的每一行是每个平面方程的法向量
    const A = new THREE.Matrix3();
    A.set(
    v12.x, v12.y, v12.z,         // 第一行应该是完整的 v12 向量
    v13.x, v13.y, v13.z,         // 第二行应该是完整的 v13 向量
    planeNormal.x, planeNormal.y, planeNormal.z // 第三行应该是完整的 planeNormal 向量
);

    // b 向量是每个平面方程的常数项
    const b1 = v12.dot(v1.clone().add(v2).multiplyScalar(0.5));
    const b2 = v13.dot(v1.clone().add(v3).multiplyScalar(0.5));
    const b3 = planeNormal.dot(v1);
    const b = new THREE.Vector3(b1, b2, b3);

    //   求解方程组，得到圆心坐标
    // 在 Three.js 中，没有直接的 solve() 函数，我们通过求逆矩阵来求解
    const A_inv = A.clone().invert();
    
    // 如果矩阵不可逆，也无法求解
    if (A_inv === null) {
        console.error("getCircle3d: Cannot invert matrix. Check input points.");
        return null;
    }
    
    const center = b.clone().applyMatrix3(A_inv);

    //   计算半径（圆心到任意一点的距离）
    const radius = center.distanceTo(v1);

    return { center, radius };
}

function getCircle3d_test(p1: Vector3, p2: Vector3, p3: Vector3): { center: Vector3, radius: number } | null {
     //   将输入点转换为 THREE.Vector3 以进行向量运算
    const v1 = p1.clone();
    const v2 = p2.clone();
    const v3 = p3.clone();

    //  计算定义平面的向量
    const v12 = v2.clone().sub(v1); // v2 - v1
    const v13 = v3.clone().sub(v1); // v3 - v1

    //   检查三点是否共线
    // 如果两个向量的叉积为零向量，则说明它们平行，三点共线
    const planeNormal = v12.clone().cross(v13);
    if (planeNormal.lengthSq() < 1e-8) {
        console.warn("getCircle3d: Three points are collinear, cannot determine a unique circle.");
        return null;
    }

    //   建立线性方程组 Ax = b 来求解圆心
    // A 矩阵的每一行是每个平面方程的法向量
    const A = new THREE.Matrix3();
    A.set(
    v12.x, v12.y, v12.z,         // 第一行应该是完整的 v12 向量
    v13.x, v13.y, v13.z,         // 第二行应该是完整的 v13 向量
    planeNormal.x, planeNormal.y, planeNormal.z // 第三行应该是完整的 planeNormal 向量
);

    // b 向量是每个平面方程的常数项
    const b1 = v12.dot(v1.clone().add(v2).multiplyScalar(0.5));
    const b2 = v13.dot(v1.clone().add(v3).multiplyScalar(0.5));
    const b3 = planeNormal.dot(v1);
    const b = new THREE.Vector3(b1, b2, b3);

    //   求解方程组，得到圆心坐标
    // 在 Three.js 中，没有直接的 solve() 函数，我们通过求逆矩阵来求解
    const A_inv = A.clone().invert();
    
    // 如果矩阵不可逆，也无法求解
    if (A_inv === null) {
        console.error("getCircle3d: Cannot invert matrix. Check input points.");
        return null;
    }
    
    const center = b.clone().applyMatrix3(A_inv);

    //   计算半径（圆心到任意一点的距离）
    const radius = center.distanceTo(v1);

    return { center, radius };
}


// 辅助函数：生成子圆弧的点 (对应 _get_sub_arc)
function getSubArc(p1: Vector3, p2: Vector3, p3: Vector3, numPoints: number = 100): Vector3[] {
    const circleInfo = getCircle3d(p1, p2, p3);
    if (!circleInfo){
      // 如果点共线，直接返回一条直线
        const linePoints: THREE.Vector3[] = [];
        for (let i = 0; i < numPoints; i++) {
            const t = i / (numPoints - 1);
            const point = new THREE.Vector3().lerpVectors(p1, p3, t);
            linePoints.push(point);
        }
        console.warn('getSubArc: Points are collinear. Returning a straight line instead of a curve.');
        return linePoints;
    };

    const { center, radius } = circleInfo;
    const OA = p1.clone().sub(center);
    const OB = p3.clone().sub(center);
    
    // 计算夹角，使用 clamp 避免数值误差
    const denom = OA.length() * OB.length();
    const cosVal = denom === 0 ? 1 : Math.max(-1, Math.min(1, OA.dot(OB) / denom));
    const OA_OB_theta = Math.acos(cosVal);

    //let planeNormal = new Vector3().crossVectors(OA, OB).normalize();
    let planeNormal = OA.clone().cross(OB);
    const planeNormal_old = planeNormal.clone();
    if (planeNormal.length() === 0) {
    // 退化处理：取任意法向量
      planeNormal = new Vector3(0, 0, 1);
      console.warn('getSubArc: planeNormal length is zero, using default normal vector.');
    } else {
      planeNormal.normalize().multiplyScalar(-1);
    }

    //console.log ('center:', center, 'radius:', radius, 'OA_OB_theta:', OA_OB_theta, 'planeNormal_old:', planeNormal_old,'planeNormal:', planeNormal);

    //const angle = OA.angleTo(OB);
    const arcPoints: Vector3[] = [];

    for (let i = 0; i < numPoints; i++) {
        const theta = (i / (numPoints - 1)) * OA_OB_theta;//angle;
        // const tempQuaternion = new THREE.Quaternion().setFromAxisAngle(planeNormal, theta);
        // const tempVector = OA.clone().applyQuaternion(tempQuaternion);
        const OT = rotateVector(OA, planeNormal, theta);
        const arcPoint = center.clone().add(OT.clone().normalize().multiplyScalar(radius));
        arcPoints.push(arcPoint);
        //const arcPoint = center.clone().add(tempVector.normalize().multiplyScalar(radius));
        //arcPoints.push(arcPoint);
    }
    return arcPoints;
}

// 辅助函数：根据XY平面交点和圆心计算三维点（_get_z_on_arc）
function getZOnArc(intersectionPointXY: THREE.Vector3, circleCenter: THREE.Vector3, radius: number): THREE.Vector3 {
     //   计算从圆心指向交点的向量 (direction = intersection_point_xy - circle_center)
    //    在 three.js 中，我们使用 .clone() 和 .sub() 方法
    //const direction = intersectionPointXY.clone().sub(circleCenter);
    const direction = new THREE.Vector3();
    direction.x = intersectionPointXY.x - circleCenter.x;
    direction.y = intersectionPointXY.y - circleCenter.y;
    direction.z = intersectionPointXY.z - circleCenter.z;
    //  将向量归一化并乘以半径 (direction / np.linalg.norm(direction) * radius)
    //    在 three.js 中，我们链式调用 .normalize() 和 .multiplyScalar()
    //direction.normalize().multiplyScalar(radius);

    //   将计算出的向量加到圆心上，得到最终的三维点 (circle_center + ...)
    //    在 three.js 中，我们使用 .clone() 和 .add() 方法
    //const intersectionPoint3d = circleCenter.clone().add(direction);

    const intersectionPoint3d = circleCenter.clone().add(direction.normalize().multiplyScalar(radius));

    return intersectionPoint3d;
}

// 辅助函数：填充曲面 (对应 _filling_surface)
function fillingSurface( curve1: BezierCurve, 
    curve2: BezierCurve, 
    A: THREE.Vector3, // 新增：用于定义平面的点 A
    D: THREE.Vector3, // 新增：用于定义平面的点 D
    O: THREE.Vector3, 
    radius: number): Vector3[] {
    const num_curve = 35;
    const filling_surface_points: THREE.Vector3[] = [];

    // 模拟 np.linspace(0, 1, num_curve)[1:-1]
    for (let i = 1; i < num_curve - 1; i++) {
        const t = i / (num_curve - 1);
        // L = curve_1.evaluate(t[i])
        const L = curve1.evaluate(t);
        // R = curve_2.evaluate(t[i])
        const R = curve2.evaluate(t);

        // AD_LR_intersection_XY = self._line_intersection_with_AD_plane(L, R)
        const AD_LR_intersection_XY = lineIntersectionWithADPlane(A, D, L, R);
        
        // 如果存在交点，则计算圆弧上的三维交点。
        if (AD_LR_intersection_XY) {
            // AD_LR_intersection_3d = self._get_z_on_arc(AD_LR_intersection_XY, O, radius)
            // 注意：这个函数的具体实现取决于你的特定逻辑。
            const AD_LR_intersection_3d = getZOnArc(AD_LR_intersection_XY, O, radius);

            // curves_point, _, _ = self._get_sub_arc(L, AD_LR_intersection_3d, R)
            const sub_arc_points = getSubArc(L, AD_LR_intersection_3d, R);
            
            // np.vstack((filling_surface_points, curves_point))
            filling_surface_points.push(...sub_arc_points);
        }
    }

    return filling_surface_points;
}

// 辅助函数：统一采样 (对应 _FPS)
function uniformSample(sample: Vector3[], num: number): Vector3[] {
    const n = sample.length;
    if (n <= num) {
        return sample; // 如果点数不足，直接返回原点云
    }

    //   计算点云的几何中心
    const center = new THREE.Vector3();
    for (const p of sample) {
        center.add(p);
    }
    center.divideScalar(n);

    const select_p: number[] = []; // 存储采样点的索引
    const L: number[] = []; // 存储点到当前采样点集的最小距离

    //  找到距离重心最远的点作为第一个采样点
    let maxDistanceSq = -1;
    let p0_index = -1;
    for (let i = 0; i < n; i++) {
        const distanceSq = sample[i].distanceToSquared(center);
        if (distanceSq > maxDistanceSq) {
            maxDistanceSq = distanceSq;
            p0_index = i;
        }
    }
    select_p.push(p0_index);

    //   初始化距离数组 L
    for (let i = 0; i < n; i++) {
        L.push(sample[p0_index].distanceToSquared(sample[i]));
    }

    //   循环选择剩余的采样点
    for (let i = 0; i < num - 1; i++) {
        let next_p_index = -1;
        let max_min_distanceSq = -1;

        for (let p_index = 0; p_index < n; p_index++) {
            const currentDistanceSq = sample[select_p[select_p.length - 1]].distanceToSquared(sample[p_index]);
            L[p_index] = Math.min(L[p_index], currentDistanceSq);

            if (L[p_index] > max_min_distanceSq) {
                max_min_distanceSq = L[p_index];
                next_p_index = p_index;
            }
        }
        
        if (next_p_index !== -1) {
            select_p.push(next_p_index);
        } else {
            break; // 无法找到更多点，提前结束
        }
    }

    //   根据索引返回采样的点
    const sampledPoints: THREE.Vector3[] = select_p.map(index => sample[index]);
    
    return sampledPoints;
}

// 辅助函数：导出点云为 PLY 文件
function exportPointsToPLY(points: THREE.Vector3[], filename: string) {
    if (points.length === 0) {
        console.warn('点云数据为空，无法导出 PLY 文件。');
        return;
    }

    // --- 1. 构建 PLY 文件头 (Header) ---
    const vertexCount = points.length;
    const header = [
        'ply',
        'format ascii 1.0',
        `element vertex ${vertexCount}`,
        'property float x',
        'property float y',
        'property float z',
        'end_header'
    ].join('\n') + '\n';

    // --- 2. 构建 PLY 文件数据体 (Data) ---
    let data = '';
    for (const p of points) {
        // 确保坐标值保留一定的小数位数，以避免文件过大
        const x = p.x.toFixed(6);
        const y = p.y.toFixed(6);
        const z = p.z.toFixed(6);
        data += `${x} ${y} ${z}\n`;
    }

    // --- 3. 创建 Blob 并触发下载 ---
    const fileContent = header + data;
    const blob = new Blob([fileContent], { type: 'text/plain' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;

    // 模拟点击下载链接
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // 释放 URL 对象
    URL.revokeObjectURL(link.href);

    console.log(`✅ PLY 文件 '${filename}' 导出成功，包含 ${vertexCount} 个点。`);
}


// 新平面绘制逻辑
function generateCustomBezierCurves(shouldDeselectAll: boolean = true) {
  // 只有在需要时才隐藏标签
  if (shouldDeselectAll) {
    deselectAll();
  }

  // 清空之前记录的曲线-关联映射
  curveAssociations = [];

  const getPointPos = (name: string) => pointMap.get(name)?.position || new THREE.Vector3();

  // 清理旧曲线
  if (curveObjects.length > 0) {
    for (let i = 0; i < curveObjects.length; i++) {
      modelGroup.remove(curveObjects[i]);
    }
    curveObjects = [];
  }

  // 清理旧的连线（如果有选中的关联，需要先隐藏其连线）
  if (selectedAssociation) {
    for (const line of selectedAssociation.lines) {
      modelGroup.remove(line);
    }
  }

   //  定义新的、显式的曲线绘制顺序
    const curveDefinitions = {
        "AB": ["A", "AB_P1", "AB_P2", "AB_P3", "AB_P4", "B"],
        "BC": ["B", "BC_P1", "BC_P2", "C"],
        "CD": ["C", "CD_P1", "CD_P2", "D"],
        "AF": ["A", "AF_P1", "AF_P2", "AF_P3", "AF_P4", "F"],
        "FE": ["F", "FE_P1", "FE_P2", "E"],
        "ED": ["E", "ED_P1", "ED_P2", "D"]
    };

    //   创建一个从“点名称”到“3D网格对象”的快速查找表，以提高效率
    const pointMap = new Map<string, THREE.Mesh>();
     sharedPointsState.positions.forEach((pos, index) => {
        if (spheres[index]) {
            pointMap.set(pos.name, spheres[index]);
        }
    });
     sharedPointsState.bezierPoints.forEach((point, index) => {
        if (bezier_points[index]) {
            pointMap.set(point.name, bezier_points[index]);
        }
    });

    

    // 获取关键点
    const A = pointMap.get("A")?.position || new THREE.Vector3();
    const D = pointMap.get("D")?.position || new THREE.Vector3();
    const B = pointMap.get("B")?.position || new THREE.Vector3();
    const F = pointMap.get("F")?.position || new THREE.Vector3();
    const C = pointMap.get("C")?.position || new THREE.Vector3();
    const E = pointMap.get("E")?.position || new THREE.Vector3();

    // 计算 AD 圆弧：优先读取共享全局 AD_arc，否则回退到 props 或默认
    const AD_arc = (typeof sharedPointsState.globalAdArc === 'number') ? sharedPointsState.globalAdArc : ((props.sceneData && typeof (props.sceneData as any).AD_arc === 'number') ? (props.sceneData as any).AD_arc : defaultADArcRad);
    const AD = D.clone().sub(A);
    const AD_arc_normal = AD.clone().cross(new THREE.Vector3(0, 0, 1)).normalize();
    const AD_rotation = AD_arc !== 0 ? AD_arc / Math.abs(AD_arc) : 0;
    
    let O = new THREE.Vector3();
    let AD_arc_radius = 0;

    {
        // 切线约束弧求解（对应 Python _solve_ad_arc_from_tangent）
        // alpha = A_tangent 角；phi = AD_arc 角；R = span / (cos(alpha) - cos(alpha+phi))
        const alpha = Math.max(1e-4, Math.min(Math.PI / 2 - 1e-4, aTangentValue.value));
        const phi_c = Math.max(1e-4, Math.min(Math.PI - 1e-4, Math.abs(AD_arc)));
        const span = AD.length();
        const adUnit = AD.clone().normalize();
        const denom = Math.cos(alpha) - Math.cos(alpha + phi_c);
        if (Math.abs(denom) > 1e-8 && span / denom > 0) {
            AD_arc_radius = span / denom;
            // 圆心 = A + R*cos(alpha)*adUnit - R*sin(alpha)*Z
            O = A.clone()
                .addScaledVector(adUnit, AD_arc_radius * Math.cos(alpha))
                .addScaledVector(new THREE.Vector3(0, 0, 1), -AD_arc_radius * Math.sin(alpha));
        } else if (AD_arc < Math.PI) {
            // 回退到旧简单公式
            const theta_ad_ao = Math.PI / 2 - Math.abs(AD_arc) / 2;
            AD_arc_radius = span / 2 / Math.cos(theta_ad_ao);
            const test = theta_ad_ao * AD_rotation;
            const AO = rotateVector(AD, AD_arc_normal, test);
            O = A.clone().add(AO.normalize().multiplyScalar(AD_arc_radius));
        } else {
            console.error('error: cannot solve arc');
        }
    }

    const OA = A.clone().sub(O);
    const AD_arc_points: THREE.Vector3[] = [];
    const numArcPoints = 100;
    for (let i = 0; i < numArcPoints; i++) {
        const theta = (i / (numArcPoints - 1)) * AD_arc;
        const OT = rotateVector(OA, AD_arc_normal, theta);
        const AD_arc_point = O.clone().add(OT.normalize().multiplyScalar(AD_arc_radius));
        AD_arc_points.push(AD_arc_point);
    }

    // 绘制 AD 弧
    const adArcGeometry = new THREE.BufferGeometry().setFromPoints(AD_arc_points);
    const adArcMaterial = new THREE.LineBasicMaterial({ color: 0xffff00 });
    const adArcObject = new THREE.Line(adArcGeometry, adArcMaterial);
    modelGroup.add(adArcObject);
    curveObjects.push(adArcObject);

    //  计算交点
    const AD_BF_intersection_XY  = lineIntersectionWithADPlane(A, D, B, F);
    const AD_CE_intersection_XY  = lineIntersectionWithADPlane(A, D, C, E);
    if (!AD_BF_intersection_XY) {
        console.warn('AD_BF_intersection_XY not found');
    } else{
      //console.log(`AD_BF_intersection_XY : "${AD_BF_intersection_XY.x},${AD_BF_intersection_XY.y},${AD_BF_intersection_XY.z}" `);
    }
    if (!AD_CE_intersection_XY) {
        console.warn('AD_CE_intersection_XY not found');
    } else{
      //console.log(`AD_CE_intersection_XY : "${AD_CE_intersection_XY.x},${AD_CE_intersection_XY.y},${AD_CE_intersection_XY.z}" `);
    }
  
     // 将 XY 平面交点映射到三维圆弧上，获取完整的三维交点
    const AD_BF_intersection_3d = AD_BF_intersection_XY ? getZOnArc(AD_BF_intersection_XY,O, AD_arc_radius) : null;
    const AD_CE_intersection_3d = AD_CE_intersection_XY ? getZOnArc(AD_CE_intersection_XY, O, AD_arc_radius) : null;

    // 绘制三维交点
    const AD_BFArcGeometry = new THREE.BufferGeometry().setFromPoints(AD_BF_intersection_3d ? [AD_BF_intersection_3d] : []);
    const AD_BFMaterial = new THREE.PointsMaterial({ color: 0x00ff00, size: 0.4 });
    const AD_BFObject = new THREE.Points(AD_BFArcGeometry, AD_BFMaterial);
    modelGroup.add(AD_BFObject);
    curveObjects.push(AD_BFObject);
    const AD_CEArcGeometry = new THREE.BufferGeometry().setFromPoints(AD_CE_intersection_3d ? [AD_CE_intersection_3d] : []);
    const AD_CEMaterial = new THREE.PointsMaterial({ color: 0x00ff00, size: 0.4 });
    const AD_CEObject = new THREE.Points(AD_CEArcGeometry, AD_CEMaterial);
    modelGroup.add(AD_CEObject);
    curveObjects.push(AD_CEObject);


    // console.log('A, D:', A, D);
    // console.log('B, F:', B, F);
    // console.log('C, E:', C, E);
    // console.log('O, AD_arc_radius:', O, AD_arc_radius);
    // console.log('AD_BF_intersection_XY:', AD_BF_intersection_XY);
    // console.log('AD_CE_intersection_XY:', AD_CE_intersection_XY);
    // console.log('AD_BF_intersection_3d:', AD_BF_intersection_3d);
    // console.log('AD_CE_intersection_3d:', AD_CE_intersection_3d);


    // 计算BF/CE圆弧
    const BF_arc_points = AD_BF_intersection_3d ? getSubArc(B, AD_BF_intersection_3d, F) : [];
    const CE_arc_points = AD_CE_intersection_3d ? getSubArc(C, AD_CE_intersection_3d, E) : [];
    // 绘制BF/CE圆弧
    const BF_arc_pointsGeometry = new THREE.BufferGeometry().setFromPoints(BF_arc_points);
    const BF_arc_pointsMaterial = new THREE.LineBasicMaterial({ color: 0xffa500 });
    const BF_arc_pointsObject = new THREE.Line(BF_arc_pointsGeometry, BF_arc_pointsMaterial);
    modelGroup.add(BF_arc_pointsObject);
    curveObjects.push(BF_arc_pointsObject);
    const CE_arc_pointsGeometry = new THREE.BufferGeometry().setFromPoints(CE_arc_points);
    const CE_arc_pointsMaterial = new THREE.LineBasicMaterial({ color: 0xffa500 });
    const CE_arc_pointsObject = new THREE.Line(CE_arc_pointsGeometry, CE_arc_pointsMaterial);
    modelGroup.add(CE_arc_pointsObject);
    curveObjects.push(CE_arc_pointsObject);

    //console.log(`BF_arc_points size: "${BF_arc_points.length}",CE_arc_points size: "${CE_arc_points.length}" `);
    
    //console.log(`AD_arc_normal : "${AD_arc_normal.x},${AD_arc_normal.y},${AD_arc_normal.z}" `);

    const curve_BC = new BezierCurve([B, getPointPos('BC_P1'), getPointPos('BC_P2'), C]);
    const curve_FE = new BezierCurve([F, getPointPos('FE_P1'), getPointPos('FE_P2'), E]);

    //   生成贝塞尔曲线点
    const FE_bezier_points = new BezierCurve([F, getPointPos('FE_P1'), getPointPos('FE_P2'), E]).getPoints(100);
    const BC_bezier_points = new BezierCurve([B, getPointPos('BC_P1'), getPointPos('BC_P2'), C]).getPoints(100);
    const AB_bezier_points = new BezierCurve([A, getPointPos('AB_P1'), getPointPos('AB_P2'), getPointPos('AB_P3'), getPointPos('AB_P4'), B]).getPoints(100);
    const CD_bezier_points = new BezierCurve([C, getPointPos('CD_P1'), getPointPos('CD_P2'), D]).getPoints(100);
    const AF_bezier_points = new BezierCurve([A, getPointPos('AF_P1'), getPointPos('AF_P2'), getPointPos('AF_P3'), getPointPos('AF_P4'), F]).getPoints(100);
    const ED_bezier_points = new BezierCurve([E, getPointPos('ED_P1'), getPointPos('ED_P2'), D]).getPoints(100);
    
    const EF_bezier_points = FE_bezier_points.slice().reverse();
    const FA_bezier_points = AF_bezier_points.slice().reverse();
    const DE_bezier_points = ED_bezier_points.slice().reverse();
    //  合并所有边缘点
    const edge_points = [...AB_bezier_points, ...BC_bezier_points, ...CD_bezier_points, ...DE_bezier_points,...EF_bezier_points, ...FA_bezier_points];
   
    //   生成曲面
    const BF_extend_points = constructSurfaceFromRotatedArc(BF_arc_points, O, AD_arc_normal, 1);
    const CE_extend_points = constructSurfaceFromRotatedArc(CE_arc_points, O, AD_arc_normal, -1);

    //console.log(`BF_extend_points size: "${BF_extend_points.length}",CE_extend_points size: "${CE_extend_points.length}" `);


    //   规则化边缘
    const A_end_regularized_edge_points = regularizeEdgeZ(BF_extend_points, [...AB_bezier_points.slice().reverse(), ...AF_bezier_points]);
    const D_end_regularized_edge_points = regularizeEdgeZ(CE_extend_points, [...CD_bezier_points, ...ED_bezier_points.slice().reverse()]);
    // 绘制A_end_regularized_edge/D_end_regularized_edge
    const A_end_regularized_edgeGeometry = new THREE.BufferGeometry().setFromPoints(A_end_regularized_edge_points);
    const A_end_regularized_edgeMaterial = new THREE.LineBasicMaterial({ color: 0x00ff00 });
    const A_end_regularized_edgeObject = new THREE.Line(A_end_regularized_edgeGeometry, A_end_regularized_edgeMaterial);
    modelGroup.add(A_end_regularized_edgeObject);
    curveObjects.push(A_end_regularized_edgeObject);
    const D_end_regularized_edgeGeometry = new THREE.BufferGeometry().setFromPoints(D_end_regularized_edge_points);
    const D_end_regularized_edgeMaterial = new THREE.LineBasicMaterial({ color: 0x00ff00 });
    const D_end_regularized_edgeObject = new THREE.Line(D_end_regularized_edgeGeometry, D_end_regularized_edgeMaterial);
    modelGroup.add(D_end_regularized_edgeObject);
    curveObjects.push(D_end_regularized_edgeObject);


    //   裁剪曲面
    // const A_end_points = cutEndSurface(BF_extend_points, edge_points);
    // const D_end_points = cutEndSurface(CE_extend_points, edge_points);

    //console.log(`A_end_points size: "${A_end_points.length}",D_end_points size: "${D_end_points.length}" `);


    // ---- AGH/JDI 侧轮廓填充曲面（对应 Python _filling_surface 新算法）----
    // 坐标系转换：侧轮廓本地偏移 (rx=宽度方向, ry=高度Z方向)
    // 宽度方向 = Z × AD_unit（垂直于AD轴，对应 Python 归一化后的 Y 轴）
    // 高度方向 = Z 轴（对应 Python 归一化后的 Z 轴）
    const _zHat = new THREE.Vector3(0, 0, 1);
    const _perpAD = _zHat.clone().cross(AD.clone().normalize()); // Z × ad_unit → "右侧"方向

    const sideA = rootSidePoints.value.find(p => p.name === 'A') ?? { x: 0, y: 0, z: 0 };
    const sideD = tipSidePoints.value.find(p => p.name === 'D') ?? { x: 0, y: 0, z: 0 };

    // 提取侧轮廓本地偏移量（相对于各自原点 A/D），对应 Python 的 Y/Z 列
    const _gahOrder = ['G', 'A_P1_G', 'A', 'A_P1_H', 'H'];
    const gahLocal = _gahOrder.map(name => {
        const sp = rootSidePoints.value.find(p => p.name === name) ?? { x: 0, y: 0, z: 0 };
        return { rx: sp.x - sideA.x, ry: sp.y - sideA.y };
    });

    const _jdiOrder = ['J', 'D_P1_J', 'D', 'D_P1_I', 'I'];
    const jdiLocal = _jdiOrder.map(name => {
        const sp = tipSidePoints.value.find(p => p.name === name) ?? { x: 0, y: 0, z: 0 };
        return { rx: sp.x - sideD.x, ry: sp.y - sideD.y };
    });

    const _numSweep = 50;
    const _numPerCurve = 50;
    const _angleMgn = Math.abs(AD_arc) / 10;
    const AGH_JDI_pts: THREE.Vector3[] = [];
    for (let si = 0; si < _numSweep; si++) {
        const tv = si / (_numSweep - 1);

        // 插值形状偏移，基点固定在 A（对应 Python 保持 X 列来自 gah，只插值 Y/Z）
        const interpCtrl = gahLocal.map((g, idx) => {
            const jdi = jdiLocal[idx];
            const rx = (1 - tv) * g.rx + tv * jdi.rx;
            const ry = (1 - tv) * g.ry + tv * jdi.ry;
            return A.clone()
                .addScaledVector(_perpAD, rx)
                .addScaledVector(_zHat, ry);
        });

        const sweepCurve = new BezierCurve(interpCtrl);
        const sweepPts = sweepCurve.getPoints(_numPerCurve);

        // 旋转角：符号取反以匹配弧方向
        // AD_arc_normal = normalize(AD×Z) ≈ -Y；弧本身沿 +Y 方向旋转
        // 故 rotatePointsAroundAxis 中的角度需取反：tv=0→+margin（A前），tv=1→-(AD_arc+margin)（D后）
        const angle = _angleMgn - tv * (Math.abs(AD_arc) + 2 * _angleMgn);
        const rotated = rotatePointsAroundAxis(sweepPts, O, AD_arc_normal, angle);
        AGH_JDI_pts.push(...rotated);
    }

    // 裁剪 AGH/JDI 填充曲面至 ABCDEF 多边形范围（对应 Python _cut_end_surface）
    const clipped_AGH_JDI = cutEndSurface(AGH_JDI_pts, edge_points);
    // 无需合并：A 根部端盖 + D 尖部端盖 + 裁剪后的 AGH/JDI 中段，只需要AGH/JDI
    // 输入 mesh 位置已旋转，无需再次旋转 ...A_end_points,...D_end_points
    const toSamplePoints = [...clipped_AGH_JDI];

    allMeshPointsForExport.value = toSamplePoints;

     // 绘制填充点
     if (toSamplePoints.length > 0) {
    const fillingPointsGeometry = new THREE.BufferGeometry().setFromPoints(toSamplePoints);
    const fillingPointsMaterial = new THREE.PointsMaterial({ color: 0x000000, size: 0.1 }); // 黑色
    const fillingPointsObject = new THREE.Points(fillingPointsGeometry, fillingPointsMaterial);
    modelGroup.add(fillingPointsObject);
    curveObjects.push(fillingPointsObject);
    }
    //   遍历您定义的每一条曲线规则（例如 "AB", "BC" ...）
    for (const curveName in curveDefinitions) {
        // 获取这条曲线需要用到的所有点的名称，并保持其顺序
        const pointNames = curveDefinitions[curveName as keyof typeof curveDefinitions];
        const currentCurveMeshes: THREE.Mesh[] = [];

        //   严格按照预定义的顺序，从查找表中获取对应的3D网格对象
        for (const pointName of pointNames) {
            const mesh = pointMap.get(pointName);
            if (mesh) {
                // 如果找到了，就将它加入到当前曲线的控制点数组中
                currentCurveMeshes.push(mesh);
            } else {
                // 如果某个点在场景中不存在，打印一个警告，避免程序崩溃
                console.warn(`绘制曲线 "${curveName}" 时，未能找到名为 "${pointName}" 的点。`);
            }
        }

        //   确保我们有足够的点（至少2个）来构成一条线段或曲线
        if (currentCurveMeshes.length >= 2) {
            // 从网格对象数组中提取出它们的位置向量
            const controlPointVectors = currentCurveMeshes.map(mesh => mesh.position);
            
            // 使用自定义的 BezierCurve 类来创建曲线
            const customCurve = new BezierCurve(controlPointVectors);

            // 生成点并渲染
            const points = customCurve.getPoints(100);
            const curveGeometry = new THREE.BufferGeometry().setFromPoints(points);
            const curveMaterial = new THREE.LineBasicMaterial({ color: 0xff00ff }); // 紫色
            const curveObject = new THREE.Line(curveGeometry, curveMaterial);
            
            modelGroup.add(curveObject);
            curveObjects.push(curveObject);
            // 不创建控制点之间的连线（贝塞尔曲线不需要显示控制点连线）
            const assocLines: THREE.Line[] = [];
            // 记录曲线与其关联的点（Meshes 与 Labels 与 Lines）
            const assocMeshes = currentCurveMeshes;
            const assocLabels = assocMeshes.map(m => getLabelForMesh(m));
            curveAssociations.push({ object: curveObject, meshes: assocMeshes, labels: assocLabels, lines: assocLines });
        } else {
            console.warn(`因点数不足，跳过绘制曲线 "${curveName}"。`);
        }
    
    }
}

// Vue 生命周期钩子
onMounted(() => {

  // Load persisted state (if any) before initializing scene so watcher can pick up points
  const persisted = loadStateFromLocalStorage();
  // 清理旧版本残留的全局 modelGroupQuaternion，避免把某个场景姿态串到其它场景
  try { clearStaleModelGroupQuaternion(); } catch (e) {}
  // 清理原始旋转缓存中不合法的历史数据，保持 scene -> rotation 映射语义稳定
  try { clearLegacyRotationCache(); } catch (e) {}


  scene = new THREE.Scene();
  modelGroup = new THREE.Group();
  scene.add(modelGroup);
  const axesHelper = new THREE.AxesHelper(100);
  modelGroup.add(axesHelper);
  const axisLabelConfigs = [
    { text: 'X', position: new THREE.Vector3(110, 0, 0), color: { r: 255, g: 80, b: 80, a: 1.0 } },
    { text: 'Y', position: new THREE.Vector3(0, 110, 0), color: { r: 80, g: 255, b: 80, a: 1.0 } },
    { text: 'Z', position: new THREE.Vector3(0, 0, 110), color: { r: 80, g: 160, b: 255, a: 1.0 } },
  ];
  axisLabelConfigs.forEach(({ text, position, color }) => {
    const label = makeTextSprite(text, { fontsize: 48, fontface: 'Arial', textColor: color });
    label.position.copy(position);
    modelGroup.add(label);
  });
  camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
  camera.position.set(0, 0, 300);
  camera.up.set(0, 1, 0);
  camera.lookAt(0, 0, 0);
  const focalLengthMM = 50.0;
  const sensorWidthMM = 36.0;
  camera.filmGauge = sensorWidthMM;      // 设置传感器宽度
  camera.setFocalLength(focalLengthMM); // 设置焦距，这会自动更新fov
  camera.updateProjectionMatrix();

  renderer = new THREE.WebGLRenderer({ antialias: true , alpha: true});
  renderer.setSize(600, 600);
  renderer.setClearColor(0x808080, 1);
  renderer.toneMapping = THREE.NoToneMapping;
  if (containerRef.value) {
      containerRef.value.appendChild(renderer.domElement)
  }

  //  --- 设置相机初始视角 ---
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableZoom = false;
  controls.enableRotate = false; // <--- 关键修改 1: 禁用旋转
  // 更新controls
  controls.update();

  // 相机固定在Z轴俯视，不再从 localStorage 恢复相机位置/四元数
  // 如果有持久化的模型旋转四元数，恢复到 modelGroup
  if (persisted) {
    try {
      if (persisted.modelGroupQuaternion && modelGroup) {
        modelGroup.quaternion.set(
          Number(persisted.modelGroupQuaternion.x) || 0,
          Number(persisted.modelGroupQuaternion.y) || 0,
          Number(persisted.modelGroupQuaternion.z) || 0,
          Number(persisted.modelGroupQuaternion.w) || 1
        );
      }
      if (controls) controls.target.set(0, 0, 0);
    } catch (e) {
      console.warn('Failed to apply persisted model state', e);
    }
  }

  // 确保在挂载时也尝试从 ORIGINAL_ROTATION_KEY 加载原始后端角度到 baseCameraEulerDeg
  try { loadOriginalBaseForScene(getSceneKey()); } catch (e) {}

  // --- 初始化几何体与材质 (赋值操作，去掉 const/let) ---
  geometry = new THREE.SphereGeometry(0.4, 16, 16);
  material = new THREE.MeshBasicMaterial({ color: 0xff0000 });
  geometry_Bezier = new THREE.SphereGeometry(0.4, 16, 16);
  material_Bezier = new THREE.MeshBasicMaterial({ color: 0x0000ff });
  // --- 正确的赋值方式 ---
  // 将创建的控制器实例赋给在顶层声明的变量
  
  dragControls = new DragControls(draggableObjects, camera, renderer.domElement);
  

  // --- 事件监听器 ---
  // 现在这里的 dragControls 和 dragControls_Bezier 引用的是正确的顶层变量
  // 所以 if 判断会通过，事件监听器会被成功附加
   // ⭐ 重构点 4: 只需一个事件监听器
    if (dragControls) {
    dragControls.addEventListener('dragstart', function (event) {
      if (controls) controls.enabled = false;
      isDragging.value = true;
      currentDragged = event.object;
      // 如果开始拖拽的是球体，记录快照以支持撤销
      const draggedObject = event.object;
      const sphereIndex = spheres.findIndex(s => s === draggedObject);
      const bezierIndexForStart = bezier_points.findIndex(p => p === draggedObject);
      if (sphereIndex !== -1 || bezierIndexForStart !== -1) {
        pushUndoSnapshot();
      }
      // 对于图片拖拽（如果允许），也可以记录快照但当前只针对球体
    });
     dragControls.addEventListener('drag', function (event) {
      // 跳过已从 scene 移除的对象
      if (!event.object.parent) return;
      // 模型组旋转后，DragControls 设置的是世界坐标，需要转回模型局部坐标
      if (modelGroup && event.object.parent === modelGroup) {
        const worldPos = new THREE.Vector3();
        event.object.getWorldPosition(worldPos);
        modelGroup.worldToLocal(worldPos);
        event.object.position.copy(worldPos);
      }
      // 在拖动过程中的每一帧，都调用 addBezier 函数重绘曲线（不隐藏标签）
      generateCustomBezierCurves(false);
      if (event.object === backgroundPlane && backgroundPlane.parent) {
        // 拖拽时实时更新相对于中心的偏移
        recordCurrentOffsets(); // 核心：拖动时同步计算新的相对位置关系
      }
      // ⭐ 新增: 拖动时更新标签位置
      const draggedObject = event.object;
      const sphereIndex = spheres.findIndex(s => s === draggedObject);
      if (sphereIndex !== -1 && sphereLabels[sphereIndex]) {
        sphereLabels[sphereIndex].position.copy(computeLabelPosition(draggedObject.position));
        // 更新对应的指示线
        const line = sphereLabelLines[sphereIndex];
        if (line) {
          (line.geometry as THREE.BufferGeometry).setFromPoints([draggedObject.position.clone(), sphereLabels[sphereIndex].position.clone()]);
          line.geometry.attributes.position.needsUpdate = true;
        }
      }
      const bezierIndex = bezier_points.findIndex(p => p === draggedObject);
       if (bezierIndex !== -1 && bezierLabels[bezierIndex]) {
        bezierLabels[bezierIndex].position.copy(computeLabelPosition(draggedObject.position));
        const bLine = bezierLabelLines[bezierIndex];
        if (bLine) {
          (bLine.geometry as THREE.BufferGeometry).setFromPoints([draggedObject.position.clone(), bezierLabels[bezierIndex].position.clone()]);
          bLine.geometry.attributes.position.needsUpdate = true;
        }
      }
    });
    dragControls.addEventListener('dragend', function (event) {
      if (controls)controls.enabled = true;
      isDragging.value = false;
      currentDragged = null;
      const draggedObject = event.object;

      const draggedMesh = event.object as THREE.Mesh;
      
      // 判断被拖拽的物体是球体还是贝塞尔点
      const sphereIndex = spheres.findIndex(s => s === draggedObject);
      if (sphereIndex !== -1) {
        // 球体位置是旋转后的显示坐标，逆旋转还原为原始数据坐标再保存
        const origPos = applyXYRotInverse(draggedObject.position);
        const positionData =  sharedPointsState.positions[sphereIndex];
        positionData.x = origPos.x;
        positionData.y = origPos.y;
        positionData.z = origPos.z;
        // 持久化状态
        saveStateToLocalStorage();
        return; // 更新完毕，退出函数
      }

      const bezierIndex = bezier_points.findIndex(p => p === draggedObject);
      if (bezierIndex !== -1) {
        // 贝塞尔点位置是旋转后的显示坐标，逆旋转还原为原始数据坐标再保存
        const origBPos = applyXYRotInverse(draggedObject.position);
        const pointData =  sharedPointsState.bezierPoints[bezierIndex];
        pointData.x = origBPos.x;
        pointData.y = origBPos.y;
        pointData.z = origBPos.z;

        // ⭐ 新增：对称点移动逻辑
        // 定义对称关系：[点1名称, 中心点名称, 点2名称]
        const symmetricPairs = [
          ['AB_P1', 'A', 'AF_P1'],
          ['AB_P4', 'B', 'BC_P1'],
          ['CD_P2', 'D', 'ED_P2'],
          ['AF_P4', 'F', 'FE_P1']
        ];

        // 检查被拖拽的点是否在对称关系中
        for (const [point1Name, centerName, point2Name] of symmetricPairs) {
          const movedPointName = pointData.name;
          let symmetricPointName: string | null = null;
          let shouldUpdate = false;

          // 判断移动的点是哪一个，确定需要更新的对称点
          if (movedPointName === point1Name) {
            symmetricPointName = point2Name;
            shouldUpdate = true;
          } else if (movedPointName === point2Name) {
            symmetricPointName = point1Name;
            shouldUpdate = true;
          }

          if (shouldUpdate && symmetricPointName) {
            // 找到中心点的坐标
            const centerPoint = sharedPointsState.positions.find(p => p.name === centerName);
            if (centerPoint) {
              // 计算对称点的新位置：对称点 = 2 * 中心点 - 移动的点
              const newSymmetricX = 2 * centerPoint.x - pointData.x;
              const newSymmetricY = 2 * centerPoint.y - pointData.y;
              const newSymmetricZ = 2 * centerPoint.z - pointData.z;

              // 更新对称点的数据
              const symmetricPointData = sharedPointsState.bezierPoints.find(p => p.name === symmetricPointName);
              if (symmetricPointData) {
                symmetricPointData.x = newSymmetricX;
                symmetricPointData.y = newSymmetricY;
                symmetricPointData.z = newSymmetricZ;

                // 同时更新3D场景中对称点的位置（需要应用 XY 旋转）
                const symmetricBezierIndex = sharedPointsState.bezierPoints.findIndex(p => p.name === symmetricPointName);
                if (symmetricBezierIndex !== -1 && bezier_points[symmetricBezierIndex]) {
                  const symDisplayPos = applyXYRotToPoint(newSymmetricX, newSymmetricY, newSymmetricZ);
                  bezier_points[symmetricBezierIndex].position.copy(symDisplayPos);

                  // 更新对称点的标签位置
                  if (bezierLabels[symmetricBezierIndex]) {
                    bezierLabels[symmetricBezierIndex].position.copy(computeLabelPosition(bezier_points[symmetricBezierIndex].position));
                    const bLine = bezierLabelLines[symmetricBezierIndex];
                    if (bLine) {
                      (bLine.geometry as THREE.BufferGeometry).setFromPoints([
                        bezier_points[symmetricBezierIndex].position.clone(),
                        bezierLabels[symmetricBezierIndex].position.clone()
                      ]);
                      bLine.geometry.attributes.position.needsUpdate = true;
                    }
                  }

                  // ⭐ 重新生成贝塞尔曲线以更新对称点对应的曲线
                  generateCustomBezierCurves(false);
                }
              }
            }
            break; // 找到匹配的对称关系后退出循环
          }
        }

        // 持久化状态
        saveStateToLocalStorage();
      }

        // 检查拖动的对象是否为背景平面（仅更新背景中心，不再修改 dataCenter）
        if (draggedMesh === backgroundPlane && props.sceneData) {
            props.sceneData.backgroundPlanePosition = {
                x: draggedMesh.position.x,
                y: draggedMesh.position.y,
                z: draggedMesh.position.z,
            };
            console.log(`图片位置已保存: x=${draggedMesh.position.x}, y=${draggedMesh.position.y}, z=${draggedMesh.position.z}`);
          // 更新独立的背景中心（不影响 dataCenter）
          try {
            bgCenter.set(draggedMesh.position.x, draggedMesh.position.y, draggedMesh.position.z);
          } catch (e) { /* ignore */ }
          // 保存到本地
          saveStateToLocalStorage();
        }

        if (event.object === backgroundPlane) {
          recordCurrentOffsets();
          saveStateToLocalStorage();
        }

      // 拖动结束后，如果之前有选中的关联，重新选择它以保持标签可见
      if (selectedAssociation) {
        const currentSelected = selectedAssociation;
        let newAssoc: CurveAssociation | undefined;
        for (const a of curveAssociations) {
          if (a.meshes.length === currentSelected.meshes.length && a.meshes.every((m, i) => m === currentSelected.meshes[i])) {
            newAssoc = a;
            break;
          }
        }
        if (newAssoc) {
          selectedAssociation = newAssoc;
          // 重新显示连线
          for (const line of newAssoc.lines) {
            line.visible = true;
          }
        }
      }
    });
  }

  // 在画布上监听点击事件（使用模块级的 onPointerDown）
  if (renderer && renderer.domElement) {
    renderer.domElement.addEventListener('pointerdown', onPointerDown as EventListener);
  }

  function animate() {
    if (!renderer) return;
    animationFrameId = requestAnimationFrame(animate);
    if (controls) {
      controls.update(); // 每一帧都更新控制器
    }
  
    // 相机已固定，背景不再需要每帧同步

    // 标签避让
    relaxLabels();
    if (renderer) {
      renderer.render(scene, camera);
    }
    
  }
  animate()

isSceneReady.value = true;
console.log('✅ ThreeScene 组件已挂载 (onMounted)。');
})

// 👇 添加这个 onUnmounted 钩子
onUnmounted(() => {
  console.log('❌ 组件正在卸载，开始清理 Three.js 资源...');
  firstCentered.value = false;
  //   停止动画循环
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
  }

  //  遍历并销毁场景中的所有对象
  if (scene) { // 确保 scene 存在
    scene.traverse(object => {
      // ⭐ 新增：在这里打印对象信息，用于第二步的调试
      console.log('正在尝试清理对象:', object.name, object.type, object);

      if (object instanceof THREE.Mesh) {
        try { // ⭐ 新增 try
          if (object.geometry) {
            object.geometry.dispose();
          }
          if (object.material) {
            if (Array.isArray(object.material)) {
              object.material.forEach(material => {
                if (material.map) material.map.dispose();
                material.dispose();
              });
            } else {
              if (object.material.map) object.material.map.dispose();
              object.material.dispose();
            }
          }
        } catch (e) { // ⭐ 新增 catch
          console.error('清理一个对象时出错，已跳过:', object, e);
        }
      }
    });
  }

  //   销毁渲染器
  if (renderer) {
    // 强制失去上下文，帮助浏览器回收资源
    renderer.forceContextLoss();
    renderer.dispose();
    
    // 从 DOM 中移除 canvas
    if (renderer.domElement && containerRef.value) {
        containerRef.value.removeChild(renderer.domElement);
    }
  }

  // 移除画布上的指针监听器
  try {
    if (renderer && renderer.domElement) {
      renderer.domElement.removeEventListener('pointerdown', onPointerDown as EventListener);
    }
  } catch (e) {
    // ignore
  }

  console.log('✅ 清理完成。');
});

type SceneData = {
  
  backgroundImage: string;
  cameraRotation: number[];
  backgroundPlanePosition: { x: number, y: number, z: number } | null;
  imageScale?: number;
};

watch(
  [() => props.sceneData, () => isSceneReady.value, () => rollAngle.value, () => zoomLevel.value] as const,
  ([newData, ready, roll, zoom]: [
      SceneData,
      boolean,
      number,
      number
    ]) => {
    if (!ready || typeof newData !== 'object' || newData === null) {
      // 如果场景未就绪，或者 newData 不是一个对象（或者为 null），则直接返回。
      return;
    }
    
    const hasKeyPoints =  sharedPointsState.positions
 &&  sharedPointsState.positions.some(p => p.name === 'F');
     if (!ready || !hasKeyPoints) {
      return; // 如果场景未就绪，或关键点A还不存在，则直接返回
    }
    //console.log("✅ 侦听器触发：场景已就绪，正在处理数据...");

    // 检测 backgroundImage 是否真正变化
    const bgImageChanged = newData.backgroundImage !== lastLoadedBgImage;
    if (bgImageChanged && newData.backgroundImage) {
      lastLoadedBgImage = newData.backgroundImage;
    }

    // 设置图片缩放比例
    imageScale.value = newData.imageScale ?? 1;

    // --- 更新球体 (positions) ---
    while ( sharedPointsState.positions.length > spheres.length) {
      if (!geometry || !material) {
        console.error("贝塞尔点的几何体或材质尚未初始化！");
        return; // 或者 break
      }
      const mesh = new THREE.Mesh(geometry, material.clone());
      const latestPos =  sharedPointsState.positions[spheres.length];
      mesh.position.set(latestPos.x, latestPos.y, latestPos.z);
      modelGroup.add(mesh);
      spheres.push(mesh);
      // 同时创建并添加标签
      const label = makeTextSprite(latestPos.name, { fontsize: 32, fontface: "Arial", textColor: {r:255, g:255, b:255, a:1.0}});
      label.position.copy(computeLabelPosition(mesh.position));
      // 默认不显示标签，点击曲线时再显示对应端点标签
      label.visible = false;
      modelGroup.add(label);
      sphereLabels.push(label);
      // 创建指示线（从球体到标签）
      const lineGeom = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), label.position.clone()]);
      const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff });
      const leader = new THREE.Line(lineGeom, lineMat);
      leader.renderOrder = 9998;
      modelGroup.add(leader);
      sphereLabelLines.push(leader);
    }
    while ( sharedPointsState.positions.length < spheres.length) {
      const removedMesh = spheres.pop();
      if (removedMesh) modelGroup.remove(removedMesh);
      const removedLabel = sphereLabels.pop();
      if (removedLabel) modelGroup.remove(removedLabel);
      const removedLine = sphereLabelLines.pop();
      if (removedLine) modelGroup.remove(removedLine);
    }
    if (!isDragging.value) {
       sharedPointsState.positions.forEach((pos, i) => {
        if (spheres[i]) {
          // 应用 XY 旋转，使 ABCDEF 点随模型一起旋转
          const displayPos = applyXYRotToPoint(Number(pos.x), Number(pos.y), Number(pos.z));
          spheres[i].position.copy(displayPos);
          if(sphereLabels[i]) {
            sphereLabels[i].position.copy(computeLabelPosition(spheres[i].position));
            const line = sphereLabelLines[i];
            if (line) {
              (line.geometry as THREE.BufferGeometry).setFromPoints([spheres[i].position.clone(), sphereLabels[i].position.clone()]);
              line.geometry.attributes.position.needsUpdate = true;
            }
          }
        }
      });
    }

    // --- 更新贝塞尔点 (bezierPoints) ---
    while ( sharedPointsState.bezierPoints.length > bezier_points.length) {
      if (!geometry_Bezier || !material_Bezier) {
        console.error("贝塞尔点的几何体或材质尚未初始化！");
        return; // 或者 break
      }
      const mesh = new THREE.Mesh(geometry_Bezier, material_Bezier.clone());
      const latestPos =  sharedPointsState.bezierPoints[bezier_points.length];
      mesh.position.set(latestPos.x, latestPos.y, latestPos.z);
      modelGroup.add(mesh);
      bezier_points.push(mesh);
      // 同时创建并添加标签
      const label = makeTextSprite(latestPos.name, { fontsize: 24, fontface: "Arial", textColor: {r:255, g:255, b:255, a:1.0}});
      label.position.copy(computeLabelPosition(mesh.position));
      // 默认隐藏贝塞尔控制点与标签，点击曲线时再显示
      mesh.visible = false;
      label.visible = false;
      modelGroup.add(label);
      bezierLabels.push(label);
      // 创建指示线（从贝塞尔点到标签）
      const bLineGeom = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), label.position.clone()]);
      const bLineMat = new THREE.LineBasicMaterial({ color: 0xffffff });
      const bleader = new THREE.Line(bLineGeom, bLineMat);
      bleader.renderOrder = 9998;
      modelGroup.add(bleader);
      bezierLabelLines.push(bleader);
    }
    while ( sharedPointsState.bezierPoints.length < bezier_points.length) {
      const removedMesh = bezier_points.pop();
      if (removedMesh) modelGroup.remove(removedMesh);
      const removedLabel = bezierLabels.pop();
      if (removedLabel) modelGroup.remove(removedLabel);
      const removedBLine = bezierLabelLines.pop();
      if (removedBLine) modelGroup.remove(removedBLine);
    }
    if (!isDragging.value) {
       sharedPointsState.bezierPoints.forEach((pos, i) => {
        if (bezier_points[i]) {
          // 应用 XY 旋转
          const displayPos = applyXYRotToPoint(Number(pos.x), Number(pos.y), Number(pos.z));
          bezier_points[i].position.copy(displayPos);
          if(bezierLabels[i]) {
            bezierLabels[i].position.copy(computeLabelPosition(bezier_points[i].position));
            const bLine = bezierLabelLines[i];
            if (bLine) {
              (bLine.geometry as THREE.BufferGeometry).setFromPoints([bezier_points[i].position.clone(), bezierLabels[i].position.clone()]);
              bLine.geometry.attributes.position.needsUpdate = true;
            }
          }
        }
      });
    }

    // 更新可拖拽对象列表
    draggableObjects = [...spheres, ...bezier_points];
    if (allowBackgroundDrag.value && backgroundPlane && backgroundPlane.parent) {
      if (!draggableObjects.includes(backgroundPlane)) {
        draggableObjects.push(backgroundPlane);
      }
    }
    if (dragControls) {
      dragControls.objects = draggableObjects;
    }

    if (!firstCentered.value) {
    // 计算所有标注点的几何中心
    const allPoints = [...spheres, ...bezier_points];
    const dataBoundingBox = new THREE.Box3();
    // const dataCenter = new THREE.Vector3();
    firstCentered.value = true;
    if (allPoints.length > 0) {
        allPoints.forEach(point => {
            dataBoundingBox.expandByObject(point);
        });
        dataBoundingBox.getCenter(dataCenter.value);
    }
    // 首次定位相机到坐标原点正上方（Z轴俯视），视点为原点
    if (camera && controls) {
      camera.position.set(0, 0, 300);
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
      controls.update();
    }
  }
    // --- 更新相机视角 (cameraRotation) ---
    const newRotation = newData.cameraRotation;
    if (modelGroup && newRotation && (newRotation.length === 3 || newRotation.length === 4)) {
      // 仅当后端的 cameraRotation 与上次应用的不同时才应用
      const needApply = !lastAppliedCameraRotation || !(
        lastAppliedCameraRotation.length === newRotation.length &&
        lastAppliedCameraRotation[0] === newRotation[0] &&
        lastAppliedCameraRotation[1] === newRotation[1] &&
        lastAppliedCameraRotation[2] === newRotation[2] &&
        (newRotation.length < 4 || lastAppliedCameraRotation[3] === newRotation[3])
      );
      if (needApply || pitchValue.value !== 0 || rollValue.value !== 0 || yawValue.value !== 0) {
        applyCameraRotationFromArray(newRotation);
        // 每次切场景都根据当前场景自己的 delta 重新叠加，避免多个场景共用同一显示姿态
        if (pitchValue.value !== 0 || rollValue.value !== 0 || yawValue.value !== 0) {
          applySlidersToCamera();
        }
      }
    }


    // 修改相机缩放 (zoomLevel)
    if (camera) {
      // 将滑块的值赋给相机的 zoom 属性
      camera.zoom = 5 * zoom; // 'zoom' 就是从依赖数组解构出来的 zoomLevel.value
      
      // !!! 关键：每次修改 zoom 或 fov 后，都必须调用此方法来使更改生效
      camera.updateProjectionMatrix();
    }

    // --- 加载背景图片 ---
    if (newData.backgroundImage && bgImageChanged) {
      const textureLoader = new THREE.TextureLoader();
      textureLoader.load(newData.backgroundImage, (texture) => {
        // 防止图片亮度提升
        texture.colorSpace = THREE.SRGBColorSpace;
        // 再次清理，确保没有残留的plane
        if (backgroundPlane) {
          // 从可拖拽列表中移除旧 plane
          draggableObjects = draggableObjects.filter(obj => obj !== backgroundPlane);
          if (dragControls) dragControls.objects = draggableObjects;
          scene.remove(backgroundPlane);
          backgroundPlane.geometry.dispose();
          if (Array.isArray(backgroundPlane.material)) {
            backgroundPlane.material.forEach(material => {
              if ('map' in material && material.map instanceof THREE.Texture) material.map.dispose();
              material.dispose();
            });
          } else {
            if ('map' in backgroundPlane.material && backgroundPlane.material.map instanceof THREE.Texture) backgroundPlane.material.map.dispose();
            backgroundPlane.material.dispose();
          }
          backgroundPlane = null;
        }

        // 根据图片比例调整平面尺寸，避免拉伸
        const imageAspectRatio = texture.image.width / texture.image.height;

        // ⭐ 关键计算：让平面尺寸与相机视野匹配
        // 这个距离决定了图片“画布”离相机有多远
        const distance = 300; 
        const BACKGROUND_IMAGE_SCALE = 0.19;//0.19;
        // 获取相机在当前距离下的视野高度
        const visibleHeight = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * distance;
        // 根据视野高度和图片比例计算视野宽度
        const visibleWidth = visibleHeight * imageAspectRatio;
      
        const BGplaneGeometry = new THREE.PlaneGeometry(visibleWidth * BACKGROUND_IMAGE_SCALE, visibleHeight * BACKGROUND_IMAGE_SCALE);
        const BGplaneMaterial = new THREE.MeshBasicMaterial({
          map: texture,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 1.0,
          // depthTest: false,
          depthWrite: false,
          toneMapped: false
        });
        backgroundPlane = new THREE.Mesh(BGplaneGeometry, BGplaneMaterial);
            // ensure stable render order and avoid z-fighting with scene geometry
        //backgroundPlane.renderOrder = -1;
      
        //   获取相机当前的朝向
        const cameraDirection = new THREE.Vector3();
        camera.getWorldDirection(cameraDirection);

        // 背景位置：优先恢复保存的位置，否则初始化为 dataCenter 前方
        if (newData.backgroundPlanePosition) {
          backgroundPlane.position.set(
            newData.backgroundPlanePosition.x,
            newData.backgroundPlanePosition.y,
            newData.backgroundPlanePosition.z
          );
        } else {
          const planeDistance = 50;
          backgroundPlane.position.copy(dataCenter.value.clone().add(cameraDirection.clone().multiplyScalar(planeDistance)));
        }

        //   让平面的旋转姿态与相机完全相同
        backgroundPlane.quaternion.copy(camera.quaternion);

        //   将平面添加到世界场景中
        scene.add(backgroundPlane);

        // 设置初始scale
        backgroundPlane.scale.set(imageScale.value, imageScale.value, 1);

        // 设置背景是否可拖拽
        if (backgroundPlane) {
          setBackgroundDraggable(allowBackgroundDrag.value);
        }

        //console.log(`背景图片已更新: ${newData.backgroundImage}`);
      }, undefined, (error) => {
        console.error(`加载背景图片失败: ${newData.backgroundImage}`, error);
      });
    }

    // --- 更新贝塞尔曲线 ---
    generateCustomBezierCurves();
  },
  {
    deep: true,
    immediate: true
  }
);

// 持久化：当 sharedPointsState 变化时保存（深度监听）
watch(
  () => ({ positions: sharedPointsState.positions, beziers: sharedPointsState.bezierPoints }),
  () => {
    saveStateToLocalStorage();
  },
  { deep: true }
);

</script>

<template>
  <div class="scene-container">
    <div ref="containerRef" class="three-canvas"></div>
    <div class="controls">
     <div class="slider-control">
        <label for="zoom-slider">缩放大小 (Zoom): {{ zoomLevel.toFixed(2) }}x</label>
        <input 
          id="zoom-slider"
          type="range" 
          min="0.1" 
          max="5" 
          step="0.1" 
          v-model.number="zoomLevel" 
        />
      </div>
      <div style="margin-top:6px;">
        <button class="action-button" @click="resetCameraToProps">回到预设视角</button>
        <button class="action-button" @click="resetImagePosition" style="margin-left: 10px;">图片复位</button>
      </div>
      <!-- 摄像机角度滑条控制：每个轴 3 个滑条 -->
      <div class="camera-sliders">
        <label>摄像机角度调整</label>
        <div class="slider-row">
          <strong>俯仰 (Pitch)</strong>
          <div style="display:flex; gap:6px; align-items:center; margin:6px 0;">
            <input type="range" :step="cameraStep" min="-180" max="180"  v-model.number="pitchValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
            <input type="number" :step="cameraStep" style="width:80px; margin-left:6px;" v-model.number="pitchValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
          </div>
        </div>
        <div class="slider-row">
          <strong>滚转 (Roll)</strong>
          <div style="display:flex; gap:6px; align-items:center; margin:6px 0;">
            <input type="range" :step="cameraStep" min="-180" max="180"  v-model.number="rollValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
            <input type="number" :step="cameraStep" style="width:80px; margin-left:6px;" v-model.number="rollValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
          </div>
        </div>
        <div class="slider-row">
          <strong>偏航 (Yaw)</strong>
          <div style="display:flex; gap:6px; align-items:center; margin:6px 0;">
            <input type="range" :step="cameraStep" min="-180" max="180" v-model.number="yawValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
            <input type="number" :step="cameraStep" style="width:80px; margin-left:6px;" v-model.number="yawValue" @input="applySlidersToCamera" @change="saveCurrentCameraRotationToProps" />
          </div>
        </div>
        <!-- <div style="margin-top:6px; display:flex; gap:8px; align-items:center;">
          <button class="action-button" @click="applySlidersToCamera">应用角度</button>
          <button class="action-button" @click="saveCurrentCameraRotationToProps">保存视角到场景</button>
        </div> -->
          <div style="margin-top:8px;">
            <label>AD_arc: {{ adArcDeg }}°</label>
            <div style="display:flex; gap:8px; align-items:center; margin-top:6px; width: 600px;">
              <input type="range" :step="0.0000000000000001" min="0" max="3.1415926" v-model.number="adArcDeg" @input="onAdArcChange" />
              <input type="number" :step="0.0000000000000001" style="width:80px;" v-model.number="adArcDeg" @change="onAdArcChange" />
              <button class="action-button" @click="resetAdArc">重置 AD_arc</button>
            </div>
          </div>
      </div>

      <!-- 新增：侧轮廓参数控制 -->
      <div class="slider-control" style="margin-top: 16px; padding: 12px; background-color: #f9f9f9; border-radius: 4px; border: 1px solid #ddd;">
        <label style="font-weight: bold; color: #333; margin-bottom: 8px; display: block;">侧轮廓参数控制</label>
        
        <div style="margin-top: 8px;">
          <label>XY Rotation: {{ (xyRotationValue * 180 / Math.PI).toFixed(5) }}°</label>
          <div style="display:flex; gap:8px; align-items:center; margin-top:4px;">
            <input
              type="range"
              min="-180"
              max="180"
              step="0.00001"
              :value="(xyRotationValue * 180 / Math.PI)"
              @input="handleXyRotationInput"
              style="flex: 5;"
            />
            <input
              type="number"
              :value="(xyRotationValue * 180 / Math.PI).toFixed(5)"
              @input="handleXyRotationInput"
              style="width:80px;"
            />
            <button class="action-button" @click="resetXyRotation">重置</button>
          </div>
        </div>

        <div style="margin-top: 12px;">
          <label>A Tangent: {{ (aTangentValue * 180 / Math.PI).toFixed(5) }}°</label>
          <div style="display:flex; gap:8px; align-items:center; margin-top:4px;">
            <input
              type="range"
              min="0"
              max="90"
              step="0.00001"
              :value="(aTangentValue * 180 / Math.PI)"
              @input="handleATangentInput"
              style="flex: 1;"
            />
            <input
              type="number"
              :value="(aTangentValue * 180 / Math.PI).toFixed(5)"
              @input="handleATangentNumberInput"
              style="width:80px;"
            />
            <button class="action-button" @click="resetATangent">重置</button>
          </div>
        </div>
      </div>

      <!-- 新增：侧轮廓窗口（固定高度防止随页面缩放拉伸） -->
      <div style="margin-top: 16px; display: flex; gap: 12px;">
        <div style="flex: 1; height: 420px; flex-shrink: 0; overflow: hidden; border: 1px solid #ccc; border-radius: 4px; padding: 8px; background-color: #fff; box-sizing: border-box;">
          <RootSideProfile
            :rootSidePoints="rootSidePoints"
            @pointUpdate="handleRootPointUpdate"
          />
        </div>
        <div style="flex: 1; height: 420px; flex-shrink: 0; overflow: hidden; border: 1px solid #ccc; border-radius: 4px; padding: 8px; background-color: #fff; box-sizing: border-box;">
          <TipSideProfile
            :tipSidePoints="tipSidePoints"
            @pointUpdate="handleTipPointUpdate"
          />
        </div>
      </div>
      <div class="slider-control">
        <label for="image-scale-slider">图片尺寸 (Image Scale): {{ imageScale.toFixed(2) }}x</label>
        <input 
          id="image-scale-slider"
          type="range" 
          min="0.1" 
          max="5" 
          step="0.01" 
          v-model.number="imageScale" 
        />
      </div>
      <div style="display:flex; gap:8px; align-items:center; margin-top:10px;">
        <button class="action-button" @click="exportPointsToPLY(allMeshPointsForExport, 'surface_points.ply')" :disabled="allMeshPointsForExport.length === 0">
          导出曲面 PLY ({{ allMeshPointsForExport.length }}点)
        </button>
        
        <div class="toggle-row" style="margin-left:12px; display:flex; align-items:center; gap:8px;">
          <label class="switch">
            <input id="bg-drag-toggle" type="checkbox" v-model="allowBackgroundDrag" />
            <span class="slider"></span>
          </label>
          <span class="toggle-label">{{ allowBackgroundDrag ? '图片拖动：已启用' : '图片拖动：已禁用' }}</span>
          <button @click="undo" :disabled="!canUndo" style="margin-left:8px;">撤销</button>
          <button @click="redo" :disabled="!canRedo" style="margin-left:4px;">还原</button>
        </div>
      </div>
      <div class="curve-buttons" style="margin-top:10px; display:flex; flex-wrap:wrap; gap:4px;">
        <button v-for="curveName in curveNames" :key="curveName" @click="selectCurveByName(curveName)" class="curve-button">{{ curveName }}</button>
      </div>
      <!-- <hr/> -->
      <!-- <button @click="addSphere">添加球体</button>
      
      <div v-for="(pos, idx) in  sharedPointsState.positions" :key="idx" class="input-group">
        <span>{{ pos.name }}:</span>
        <input v-model.number="pos.x" type="number" />
        <input v-model.number="pos.y" type="number" />
        <input v-model.number="pos.z" type="number" />
        <button @click="removeSphere(idx)">删除</button>
      </div> -->
      <!-- <hr/> -->
      <!-- <input v-model="bezierPointName" placeholder="控制点名称" />
      <button @click="addBezierPoint(bezierPointName)">添加贝塞尔点</button>
      <div v-for="(point, idx) in  sharedPointsState.bezierPoints
" :key="idx" class="input-group-bezier">
        <span>{{ point.name }}:</span>
        <input v-model.number="point.x" type="number" />
        <input v-model.number="point.y" type="number" />
        <input v-model.number="point.z" type="number" />
        <button @click="removeBezierPoint(idx)">删除</button>
      </div> -->
    </div>
    
  </div>
</template>

<style scoped>

/* 新增：为滑块添加样式 */
.slider-control {
  display: flex;
  flex-direction: column;
  margin-bottom: 10px;
  width: 600px;
}

.slider-control label {
  margin-bottom: 5px;
}

.slider-control input,
#roll-slider {
  width: 100%;            /* 占满父容器宽度 */
  max-width: 800px;       /* 可选，限制最大宽度，按需调整或删除 */
  box-sizing: border-box; /* 包含内边距 */
  height: 24px;           /* 可选：增高滑条轨道 */
}

.scene-container {
  display: flex;           /* 开启横向排列 */
  flex-direction: row;     /* 左边是画布，右边是控件 */
  align-items: flex-start; /* 顶部对齐 */
  gap: 20px;               /* 左右两者之间的间距 */
  
  border: 1px solid #ccc;
  padding: 10px;
  margin-bottom: 10px;
}

/* Toggle switch styles */
.switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 26px;
}
.switch input { 
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .2s;
  border-radius: 26px;
}
.slider:before {
  position: absolute;
  content: "";
  height: 20px;
  width: 20px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .2s;
  border-radius: 50%;
}
.switch input:checked + .slider {
  background-color: #4CAF50;
}
.switch input:checked + .slider:before {
  transform: translateX(22px);
}
.toggle-label {
  font-size: 13px;
  color: #333;
}
.action-button {
  padding: 6px 12px;
  background-color: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.action-button:disabled {
  background-color: #9E9E9E;
  cursor: not-allowed;
}
.controls {
  flex-grow: 1;           /* 占据右侧剩余空间 */
  /* 不设 max-height / overflow，让内容自然撑开，无需滚动条 */
  margin-bottom: 0;
}
.three-canvas {
  width: 600px;
  height: 800px;          /* 纵向拉长画布，与右侧控件区等高 */
  flex-shrink: 0;
  background-color: #808080;
}
.input-group, .input-group-bezier {
    display: flex;
    gap: 5px;
    margin-bottom: 5px;
}
input {
    width: 60px;
}

.curve-button {
  padding: 4px 8px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.curve-button:hover {
  background-color: #0056b3;
}
/* 摇杆样式 */
.camera-sliders { margin: 8px 0; }
.camera-sliders .slider-row { margin-bottom: 6px; width: 600px; }
.camera-sliders input[type="range"] { width: 100%; }
</style>