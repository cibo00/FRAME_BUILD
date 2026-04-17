<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { DragControls } from 'three/examples/jsm/controls/DragControls.js'
import { FontLoader } from 'three/examples/jsm/loaders/FontLoader.js'
import { TextGeometry } from 'three/examples/jsm/geometries/TextGeometry.js'
import {api_vedio} from '@/api.js';
import {api} from '@/api.js';
import { Const, string } from 'three/tsl'
import SidePanel from './components/SidePanel.vue'
import ThreeScene from './components/ThreeScene.vue'
import { sharedPointsState, type ScenePoint } from './stores/sharedStore.ts';
import { OperationManager } from '@/utils/OperationManager';
import { getTabScopedId } from '@/utils/clientId';
const str_point = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

// 操作管理器实例
let operationManager: OperationManager | null = null;

// 用于存放从后端获取并转换后的场景数据，将传递给SidePanel
const scenesData = ref<any[]>([]);
// 本地持久化的 storage key，模块级可在本文件任意位置引用（加 tabScope 后缀实现标签页隔离）
const tabScope = getTabScopedId();
const STORAGE_KEY = `frame_build_three_scene_state_v1_${tabScope}`;
//const isLoading = ref(false);
const errorMessage = ref('');

// --- 数据类型定义 ---
// 为了代码清晰和类型安全，我们定义与Go后端匹配的TypeScript接口
interface Metadata {
  image_filename: string;
  instance_rotation_euler_degrees: number[];
  quaternion?: number[];
}

interface ImageWithMetadata {
  imageUrl: string;
  metadata: Metadata;
}

interface OutputData {
  [key: string]: number[] | number; // 允许字符串索引
}

interface ApiResponse {
  images: ImageWithMetadata[];
  outputData: OutputData;
}

interface Vector2 { x: number; y: number; }
interface Vector3 { x: number; y: number; z: number; }

interface SceneObject {
    positions?: { name: string, x: number, y: number, z: number }[]; 
    bezierPoints?: { name: string, x: number, y: number, z: number }[];
    backgroundImage: string;
    cameraRotation: number[];
  AD_arc?: number;
    
}

// 定义保存时的负载结构
interface SceneSaved {
  backgroundImage: string;
  cameraRotation: number[];
  backgroundPlanePosition?: { x: number; y: number; z: number } | null;
}

interface LocalSavePayload {
    positions: ScenePoint[];
    bezierPoints: ScenePoint[];
  scenes: SceneSaved[];
  globalADArc?: number;
  sideProfilePoints?: ScenePoint[];
  xyRotation?: number | null;
  aTangent?: number | null;
}

const curveObject: THREE.Line | null = null

const curveObjects: THREE.Line[] = []

// 标记是否已经从 localStorage 恢复过数据（用于决定是否在后端失败时展示错误）
let haveLocalRestore = false;

// 视频相关
let userId = ''
// --- 状态变量 ---
const isLoading_Vedio = ref(false);
const uploadProgress = ref(0);
const message = ref('');
const fileName = ref('');
// 创建一个 ref 来引用模板中的 <input> 元素
// const fileInputRef = ref(null);
const fileInputRef = ref<HTMLInputElement | null>(null)

// 注册数据
const register_data = ref ([{username: '',
      password: '',
      error: null}])

// 登录数据
const login_data = ref ([{username: '',
      password: '',
      error: null}])

const Three_Vector = ref({
  x: 0,
  y: 0,
  z: 0
})

const result = ref ([{
  point_name: '',
  Three_Vector : Three_Vector.value,
}])

const Send_Building_Result = ref ({
  user_name : '',
  result : result.value,
})

// 新边栏场景数据
const sideScenesData = ref([
  // 第一个场景的数据
  {
    positions: [{ name: 'A', x: 1, y: 1, z: 0 }],
    bezierPoints: [],
  },
  // 第二个场景的数据
  {
    positions: [{ name: 'A', x: -2, y: 3, z: 1 }],
    bezierPoints: [],
  },
  // 您可以按需添加更多场景
]);



async function test_login(username_login : string, password_login : string ) {

    // 发送登录请求
  try {
        const response = await api.post('/Login', {
          username: username_login,
          password: password_login,
        });

        userId = username_login

        // 登录成功后，从响应中获取 token
        const token = response.data.session_token;

        if (token) {
          // **步骤 A: 将 Token 存入 localStorage**
          localStorage.setItem('session_token', token);

          console.log('登录成功，Token 已存储!');

          // 初始化操作管理器
          await initOperationManager(token);

          // 登录成功后可以跳转到其他页面
          // this.$router.push('/profile');
        }
      } catch (err) {
        // this.error = '登录失败，请检查用户名和密码。';
        console.error(err);
      }
}

/**
 * 初始化操作管理器
 */
async function initOperationManager(token: string) {
  try {
    // 创建操作管理器实例
    operationManager = new OperationManager(token);

    console.log('[App] 操作管理器初始化成功');

    // 初始化并尝试恢复临时操作
    const savedData = await operationManager.init();

    if (savedData) {
      console.log('[App] 恢复的临时操作数据:', savedData);

      // 恢复共享点数据
      if (savedData.positions && Array.isArray(savedData.positions)) {
        sharedPointsState.positions = savedData.positions;
      }
      if (savedData.bezierPoints && Array.isArray(savedData.bezierPoints)) {
        sharedPointsState.bezierPoints = savedData.bezierPoints;
      }

      // 恢复场景数据
      if (savedData.scenes && Array.isArray(savedData.scenes)) {
        scenesData.value = savedData.scenes;
      }

      // 恢复全局AD_arc
      if (savedData.globalADArc !== undefined) {
        (sharedPointsState as any).globalAdArc = savedData.globalADArc;
      }

      // 恢复 localStorage 数据
      if (savedData.mainState) {
        setLocalStorageItem('frame_build_three_scene_state_v1', savedData.mainState);
      }
      if (savedData.originalRotationMap) {
        setLocalStorageItem('frame_build_three_scene_state_v1_original_camera_rotation_map', savedData.originalRotationMap);
      }
      if (savedData.globalAdArcValue !== null && savedData.globalAdArcValue !== undefined) {
        setLocalStorageItem('frame_build_three_scene_state_v1_global_adarc', savedData.globalAdArcValue);
      }
      if (savedData.originalAdArcMap) {
        setLocalStorageItem('frame_build_three_scene_state_v1_original_adarc_map', savedData.originalAdArcMap);
      }
      if (savedData.cameraDeltaMap) {
        setLocalStorageItem('frame_build_three_scene_state_v1_camera_delta_map', savedData.cameraDeltaMap);
      }

      console.log('[App] 已恢复临时操作状态（包括 localStorage 数据）');
    } else {
      // 没有找到临时操作，说明用户已超时或关闭网页，清除所有 localStorage 数据
      console.log('[App] 没有找到临时操作，清除所有 localStorage 数据');
      clearAllLocalStorageData();
    }

    // 启动 localStorage 监听器
    setupLocalStorageListener();

  } catch (error) {
    console.error('[App] 初始化操作管理器失败:', error);
    // 初始化失败，清除 token
    localStorage.removeItem('session_token');
    clearAllLocalStorageData();
    errorMessage.value = '初始化失败，请重新登录';
    operationManager = null;
  }
}

/**
 * 清除所有相关的 localStorage 数据
 */
function clearAllLocalStorageData() {
  try {
    const keysToRemove = [
      STORAGE_KEY,
      STORAGE_KEY + '_original_camera_rotation_map',
      STORAGE_KEY + '_global_adarc',
      STORAGE_KEY + '_original_adarc_map',
      STORAGE_KEY + '_camera_delta_map'
    ];

    keysToRemove.forEach(key => {
      localStorage.removeItem(key);
      console.log(`[App] 已清除 localStorage 键: ${key}`);
    });

    // 清空共享点数据
    sharedPointsState.positions = [];
    sharedPointsState.bezierPoints = [];
    scenesData.value = [];
    (sharedPointsState as any).globalAdArc = undefined;

    console.log('[App] 所有 localStorage 数据已清除');
  } catch (error) {
    console.error('[App] 清除 localStorage 数据失败:', error);
  }
}

async function test_register (username_register : string, password_register : string ) {
  
    // 发送登录请求
  try {
        // 3. 使用 api.post 发送请求。
        //    - 第一个参数是相对路径 '/register'
        //    - 第二个参数是要发送的 JS 对象，Axios 会自动处理它
        const response = await api.post('/Register', {
          username: username_register,
          password: password_register,
        });

        // 4. 处理成功响应
        //    Axios 将成功的响应体放在 response.data 中
        const successMessage = response.data; // 假设后端直接返回 "用户注册成功" 字符串
        console.log('注册成功:', successMessage);

        // 可以在这里添加跳转到登录页的逻辑
        // setTimeout(() => this.$router.push('/login'), 2000);

      } catch (error) {
        if (typeof error === 'object' && error !== null) {
          // 你可以进一步判断 error 是否有 response/message 属性
          if ('response' in error) {
            // @ts-ignore
            console.error('服务器响应错误:', error.response)
          } else if ('request' in error) {
            // @ts-ignore
            console.error('网络错误:', error.request)
          } else if ('message' in error) {
            // @ts-ignore
            console.error('未知错误:', error.message)
          } else {
            console.error('未知错误:', error)
          }
        } else {
          console.error('未知错误:', error)
        }
    }
}

// 添加球体


// 生成贝塞尔曲线
function addBezier ()
{
  
}

// 三维初始化
onMounted(() => {

})

// 监听共享点数据变化，自动保存临时操作
watch(
  () => [sharedPointsState.positions, sharedPointsState.bezierPoints, scenesData.value],
  () => {
    saveAllDataToBackend();
  },
  { deep: true }
);

// 辅助函数：从 localStorage 读取数据
function getLocalStorageItem(key: string): any {
  try {
    const value = localStorage.getItem(key);
    if (value) {
      try {
        return JSON.parse(value);
      } catch {
        return value; // 如果不是 JSON，返回原始字符串
      }
    }
  } catch (error) {
    console.error(`读取 localStorage 键 ${key} 失败:`, error);
  }
  return null;
}

// 辅助函数：设置 localStorage 数据
function setLocalStorageItem(key: string, value: any): void {
  try {
    if (value === null || value === undefined) {
      localStorage.removeItem(key);
    } else if (typeof value === 'string') {
      localStorage.setItem(key, value);
    } else {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch (error) {
    console.error(`设置 localStorage 键 ${key} 失败:`, error);
  }
}

// 组件卸载前清理
onBeforeUnmount(() => {
  if (operationManager) {
    operationManager.destroy();
  }
  // 移除 localStorage 监听器
  if (localStorageListener) {
    window.removeEventListener('storage', localStorageListener);
  }
});

// localStorage 监听器
let localStorageListener: ((e: StorageEvent) => void) | null = null;

// 设置 localStorage 监听器，当 localStorage 变化时自动保存
function setupLocalStorageListener() {
  // 创建一个防抖的保存函数
  let saveTimeout: number | null = null;
  const debouncedSave = () => {
    if (saveTimeout !== null) {
      clearTimeout(saveTimeout);
    }
    saveTimeout = window.setTimeout(() => {
      saveAllDataToBackend();
    }, 1000); // 1秒防抖
  };

  // 监听 storage 事件（跨标签页的变化）
  localStorageListener = (e: StorageEvent) => {
    if (e.key && e.key.startsWith('frame_build_three_scene_state')) {
      console.log('[App] 检测到 localStorage 变化:', e.key);
      debouncedSave();
    }
  };
  window.addEventListener('storage', localStorageListener);

  // 使用 MutationObserver 或定期检查来监听同一标签页内的 localStorage 变化
  // 由于浏览器不会为同一标签页触发 storage 事件，我们需要另一种方法
  // 这里我们使用定期检查的方式
  let lastSavedData = '';
  setInterval(() => {
    if (operationManager) {
      const currentData = JSON.stringify({
        mainState: getLocalStorageItem('frame_build_three_scene_state_v1'),
        originalRotationMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_camera_rotation_map'),
        globalAdArcValue: getLocalStorageItem('frame_build_three_scene_state_v1_global_adarc'),
        originalAdArcMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_adarc_map'),
        cameraDeltaMap: getLocalStorageItem('frame_build_three_scene_state_v1_camera_delta_map'),
      });

      if (currentData !== lastSavedData) {
        lastSavedData = currentData;
        debouncedSave();
      }
    }
  }, 2000); // 每2秒检查一次
}

// 保存所有数据到后端（临时操作，含修正四元数）
function saveAllDataToBackend() {
  if (!operationManager) return;

  const operationData = {
    positions: sharedPointsState.positions,
    bezierPoints: sharedPointsState.bezierPoints,
    scenes: scenesData.value.map(scene => ({
      ...scene,
      correctedQuaternion: getCorrectedQuaternion(scene),
    })),
    globalADArc: (sharedPointsState as any).globalAdArc,
    globalSettings: {
      finger_type: sharedPointsState.fingerType,
      focal_length_mm: sharedPointsState.focalLengthMm,
      sensor_width_mm: sharedPointsState.sensorWidthMm,
    },

    mainState: getLocalStorageItem('frame_build_three_scene_state_v1'),
    originalRotationMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_camera_rotation_map'),
    globalAdArcValue: getLocalStorageItem('frame_build_three_scene_state_v1_global_adarc'),
    originalAdArcMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_adarc_map'),
    cameraDeltaMap: getLocalStorageItem('frame_build_three_scene_state_v1_camera_delta_map'),

    timestamp: Date.now()
  };

  operationManager.saveTempOperation(operationData);
}

// 保存结果至服务器
async function Save_Building_Result() {
  try {
    // 使用与本地保存相同的后端格式
    const payload = {
      global_settings: {
        finger_type: sharedPointsState.fingerType || '',
        focal_length_mm: sharedPointsState.focalLengthMm || 0,
        sensor_width_mm: sharedPointsState.sensorWidthMm || 0,
      },
      output_data: buildOutputData(),
      image_metadata_list: buildImageMetadataList(),
    };

    const sendPayload = {
      user_name: userId || 'anonymous',
      result: payload,
    };

    const response = await api.post('/api/Save_BuildingResult_AsJson', sendPayload);

    if (response.status === 201 || response.status === 200) {
      alert('结果已成功保存至服务器！');
      console.log('保存成功，记录ID:', response.data);
    } else {
      alert('保存失败，请重试');
      console.error('保存失败:', response.status);
    }
  } catch (error) {
    console.error('保存结果到服务器失败:', error);
    alert('保存失败，请检查网络连接或联系管理员。');
  }
}

const isSaving = ref(false); // 保存状态

// 图片相关响应式变量
const imageUrls = ref<string[]>([])
const isLoading = ref(false)

// 获取图片并加载到 three.js 场景
async function fetchNextThreeImages() {
  
}

/**
 * 将从Go后端接收的OutputData转换为前端ThreeScene所需的数据格式。
 * 这个函数的逻辑直接翻译自您提供的 nailmodel.py。
 * @param outputData 从API接收的原始output data
 * @returns 转换后的 positions 和 bezierPoints 数组
 */

/**
 * 核心转换函数：将后端返回的单个OutputData和单个ImageWithMetadata
 * 转换为前端ThreeScene组件可以直接使用的数据格式。
 */
function transformOutputData(outputData: OutputData, imageWithMeta: ImageWithMetadata): SceneObject {
    const allPoints: { [key: string]: Vector3 } = {};

    // ⭐ 步骤 2: 直接遍历 outputData 对象本身
    for (const key in outputData) {
        // 跳过非点位属性
        if (key === 'AD_arc' || key === 'Filename') {
            continue;
        }

        const p = outputData[key];

        // 使用 "类型守卫" 来确保 p 是一个数组，这会消除 TypeScript 错误
        if (Array.isArray(p) && p.length >= 2) {
            allPoints[key] = { x: p[0], y: p[1], z: p.length >= 3 ? p[2] : 0 };
        }
        
    }

    // 2. 根据Python逻辑计算派生点 (这部分逻辑保持不变)
    if (allPoints['A'] && allPoints['A_P_AF']) {
        allPoints['AB_P1'] = {
            x: allPoints['A'].x + (allPoints['A'].x - allPoints['A_P_AF'].x),
            y: allPoints['A'].y + (allPoints['A'].y - allPoints['A_P_AF'].y),
            z: allPoints['A'].z + (allPoints['A'].z - allPoints['A_P_AF'].z),
        };
    }
    if(allPoints['B_P_AB']) allPoints['AB_P4'] = allPoints['B_P_AB'];
    if(allPoints['B'] && allPoints['B_P_AB']) {
         allPoints['BC_P1'] = {
            x: allPoints['B'].x + (allPoints['B'].x - allPoints['B_P_AB'].x),
            y: allPoints['B'].y + (allPoints['B'].y - allPoints['B_P_AB'].y),
            z: allPoints['B'].z + (allPoints['B'].z - allPoints['B_P_AB'].z),
        };
    }
    if(allPoints['D_P_CD']) allPoints['CD_P2'] = allPoints['D_P_CD'];
    if(allPoints['A_P_AF']) allPoints['AF_P1'] = allPoints['A_P_AF'];
    if(allPoints['F_P_AF']) allPoints['AF_P4'] = allPoints['F_P_AF'];
    if(allPoints['F'] && allPoints['F_P_AF']) {
        allPoints['FE_P1'] = {
            x: allPoints['F'].x + (allPoints['F'].x - allPoints['F_P_AF'].x),
            y: allPoints['F'].y + (allPoints['F'].y - allPoints['F_P_AF'].y),
            z: allPoints['F'].z + (allPoints['F'].z - allPoints['F_P_AF'].z),
        };
    }
    if(allPoints['D'] && allPoints['D_P_CD']) {
        allPoints['ED_P2'] = {
            x: allPoints['D'].x + (allPoints['D'].x - allPoints['D_P_CD'].x),
            y: allPoints['D'].y + (allPoints['D'].y - allPoints['D_P_CD'].y),
            z: allPoints['D'].z + (allPoints['D'].z - allPoints['D_P_CD'].z),
        };
    }
    
    // 3. 将点分类为 positions 和 bezierPoints (这部分逻辑保持不变)
    const processedPositions: { name: string, x: number, y: number, z: number }[] = [];
    const processedBezierPoints: { name: string, x: number, y: number, z: number }[] = [];

    const positionNames = ["A", "B", "C", "D", "E", "F"];
    // 定义一个要从 bezierPoints 中排除的点名列表
    const pointsToExclude = ["A_P_AF", "B_P_AB", "D_P_CD", "F_P_AF"];

    for (const name in allPoints) {
        if (positionNames.includes(name)) {
            processedPositions.push({ name, ...allPoints[name] });
        } else {
             if (!pointsToExclude.includes(name)) {
                processedBezierPoints.push({ name, ...allPoints[name] });
            }
        }
    }

    // 4. 计算相机旋转：优先使用四元数（直接传递），回退到欧拉角
    let cameraRotation: number[];
    const meta = imageWithMeta.metadata;
    if (meta.quaternion && meta.quaternion.length === 4) {
        // 直接传递四元数，由 ThreeScene 内部转换并应用变换
        cameraRotation = meta.quaternion;
    } else {
        cameraRotation = meta.instance_rotation_euler_degrees;
    }

    // 5. 返回最终的、可以直接给ThreeScene使用的数据对象
    return {
        positions: processedPositions,
        bezierPoints: processedBezierPoints,
        backgroundImage: imageWithMeta.imageUrl,
        cameraRotation: cameraRotation,
        AD_arc: typeof outputData['AD_arc'] === 'number' ? (outputData['AD_arc'] as number) : undefined,
    };
}

// 计算每个场景的修正四元数（原始四元数 + 滑条增量）
function getCorrectedQuaternion(scene: any): number[] {
  const tabScope = getTabScopedId();
  const deltaMapKey = `frame_build_three_scene_state_v1_${tabScope}_camera_delta_map`;
  const rot = scene.cameraRotation;

  // 非4元素时直接返回原始值
  if (!rot || rot.length !== 4) return rot;

  const qBase = new THREE.Quaternion(rot[0], rot[1], rot[2], rot[3]);

  // 读取该场景的滑条增量
  const sceneKey = scene.backgroundImage || 'default_scene';
  let pitchDelta = 0, yawDelta = 0, rollDelta = 0;
  try {
    const raw = localStorage.getItem(deltaMapKey);
    if (raw) {
      const map = JSON.parse(raw);
      const entry = map[sceneKey];
      if (entry) {
        pitchDelta = entry.pitchDelta || 0;
        yawDelta = entry.yawDelta || 0;
        rollDelta = entry.rollDelta || 0;
      }
    }
  } catch (e) {}

  // 无增量时直接返回原始四元数
  if (pitchDelta === 0 && yawDelta === 0 && rollDelta === 0) return rot;

  // 与 ThreeScene 中 applySlidersToCamera 一致：先转欧拉角作为 base，再用增量叠加
  const baseEulerDeg = [0, 0, 0];
  const eulerRad = new THREE.Euler().setFromQuaternion(qBase, 'XYZ');
  const toDeg = 180 / Math.PI;
  baseEulerDeg[0] = eulerRad.x * toDeg;
  baseEulerDeg[1] = eulerRad.y * toDeg;
  baseEulerDeg[2] = eulerRad.z * toDeg;

  const baseQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(
    THREE.MathUtils.degToRad(baseEulerDeg[0]),
    THREE.MathUtils.degToRad(baseEulerDeg[1]),
    THREE.MathUtils.degToRad(baseEulerDeg[2]),
    'XYZ'
  ));
  const deltaQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(
    THREE.MathUtils.degToRad(pitchDelta),
    THREE.MathUtils.degToRad(yawDelta),
    THREE.MathUtils.degToRad(rollDelta),
    'YXZ'
  ));
  const corrected = baseQ.clone().multiply(deltaQ);
  return [corrected.x, corrected.y, corrected.z, corrected.w];
}

// 从 scenesData 构建 output_data（后端格式，点名为 key，坐标为 [x, y]）
function buildOutputData(): Record<string, any> {
  const nameReplaceMap: { [key: string]: string } = {
    'AB_P4': 'B_P_AB', 'CD_P2': 'D_P_CD', 'AF_P1': 'A_P_AF', 'AF_P4': 'F_P_AF'
  };

  const output: Record<string, any> = {};

  // 合并 positions 和 bezierPoints（仅取 x, y）
  const allPoints = [...sharedPointsState.positions, ...sharedPointsState.bezierPoints];
  for (const p of allPoints) {
    const name = nameReplaceMap[p.name] || p.name;
    output[name] = [p.x, p.y];
  }

  // 侧轮廓控制点
  if (sharedPointsState.sideProfilePoints) {
    for (const p of sharedPointsState.sideProfilePoints) {
      output[p.name] = [p.x, p.y];
    }
  }

  // 标量参数
  if (typeof sharedPointsState.globalAdArc === 'number') {
    output['AD_arc'] = sharedPointsState.globalAdArc;
  }
  if (typeof sharedPointsState.xyRotation === 'number') {
    output['xy_rotation'] = sharedPointsState.xyRotation;
  }
  if (typeof sharedPointsState.aTangent === 'number') {
    output['A_tangent'] = sharedPointsState.aTangent;
  }

  return output;
}

// 构建 image_metadata_list（每个场景一个条目，包含修正后的四元数）
function buildImageMetadataList(): { image_filename: string; quaternion: number[] }[] {
  return scenesData.value.map(scene => {
    const corrected = getCorrectedQuaternion(scene);
    const filename = scene.backgroundImage ? scene.backgroundImage.split('/').pop() : '';
    return {
      image_filename: filename,
      quaternion: corrected,
    };
  });
}

// 下载 JSON 文件（后端 testdata.json 格式）
function saveAllPointsData() {
    isSaving.value = true;

    try {
        const payload = {
          global_settings: {
            finger_type: sharedPointsState.fingerType || '',
            focal_length_mm: sharedPointsState.focalLengthMm || 0,
            sensor_width_mm: sharedPointsState.sensorWidthMm || 0,
          },
          output_data: buildOutputData(),
          image_metadata_list: buildImageMetadataList(),
        };

        const dataStr = JSON.stringify(payload, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `testdata_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        URL.revokeObjectURL(url);

        alert('数据已成功保存为 JSON 文件！');

    } catch (error) {
        console.error('生成或下载 JSON 文件失败:', error);
        alert('文件下载失败，请检查浏览器设置或联系管理员。');
    } finally {
        isSaving.value = false;
    }
}


// 仅从后端获取参数（xy_rotation、A_tangent 等），不覆盖已有的 positions/bezierPoints/scenes
async function fetchAndUpdateParams() {
  try {
    // 使用不消耗数据组的专用接口，避免多用户并发时耗尽 currentGroupIndex
    const response = await api.get('/api/current-params');
    const data = response.data as any;
    if (data.outputData) {
      const od = data.outputData as any;
      if (typeof od['xy_rotation'] === 'number') {
        sharedPointsState.xyRotation = od['xy_rotation'];
        console.log('[App] fetchAndUpdateParams: xyRotation =', od['xy_rotation']);
      }
      if (typeof od['A_tangent'] === 'number') {
        sharedPointsState.aTangent = od['A_tangent'];
        console.log('[App] fetchAndUpdateParams: aTangent =', od['A_tangent']);
      }
    }
  } catch (e) {
    console.warn('[App] fetchAndUpdateParams failed:', e);
  }
}

async function fetchNextDataBatch(force = false) {
  isLoading.value = true;
  errorMessage.value = '';

  // 如果是强制获取（点击"获取下一组"按钮），清除临时操作
  if (force && operationManager) {
    console.log('[App] 清除临时操作...');
    await operationManager.clearTempOperation();
  }

  try {
    // 假设您的api实例已经配置好了Authorization请求头
    const response = await api.get('/api/next-three-image-and-data');
    // 如果服务器返回 HTML（例如 index.html），content-type 可能为 text/html
    const contentType = response.headers && (response.headers['content-type'] || response.headers['Content-Type']);
    if (typeof contentType === 'string' && contentType.indexOf('text/html') !== -1) {
      throw new Error('后端返回 HTML 页面（可能是未找到或代理错误），而非 JSON。');
    }
    const apiData = response.data as ApiResponse;

    // 新增: 防御性检查，确保收到的数据结构正确
    if (!apiData || !Array.isArray(apiData.images)) {
      // 在控制台记录收到的错误数据，方便调试
      console.error("收到的API数据格式不正确:", apiData);
      // 抛出一个更明确的错误
      throw new Error("从服务器返回的数据格式不正确，缺少'images'数组。");
    }

    // 清空旧数据
    //scenesData.value = [];
    
    const newScenes = [];
    let initialPositions: ScenePoint[] = [];    // 用于存放第一个场景的点数据
    let initialBezierPoints: ScenePoint[] = []; // 用于存放第一个场景的贝塞尔点数据
    // 关键点：遍历后端返回的 images 数组
    for (const imageWithMeta of apiData.images) {
      // 对每一张图片，都使用【同一个 outputData】和【它自己独特的 imageWithMeta】
      // 来调用转换函数，生成一个包含独特相机视角的场景对象
      const scene = transformOutputData(apiData.outputData, imageWithMeta);
      if (newScenes.length === 0) {
        // 确保数据存在，并提取
        initialPositions = scene.positions || [];
        initialBezierPoints = scene.bezierPoints || [];
      }
      newScenes.push(scene);
    }
    
    // 2. 初始化全局共享状态 (仅在未初始化时执行)
        if (sharedPointsState.positions.length === 0 && initialPositions.length > 0) {
            // 使用深拷贝来避免引用问题
            sharedPointsState.positions = initialPositions.map(p => ({ ...p }));
            sharedPointsState.bezierPoints = initialBezierPoints.map(p => ({ ...p }));
            console.log("✅ 全局共享点数据已初始化。");
        }

        // 始终从后端 outputData 更新可选参数（不受 localStorage 缓存影响）
        if (apiData.outputData) {
          const od = apiData.outputData as any;
          console.log('[App] outputData keys:', Object.keys(od));
          console.log('[App] xy_rotation:', od['xy_rotation'], 'A_tangent:', od['A_tangent']);
          if (typeof od['xy_rotation'] === 'number') {
            sharedPointsState.xyRotation = od['xy_rotation'];
            console.log('[App] Set sharedPointsState.xyRotation =', od['xy_rotation']);
          }
          if (typeof od['A_tangent'] === 'number') {
            sharedPointsState.aTangent = od['A_tangent'];
            console.log('[App] Set sharedPointsState.aTangent =', od['A_tangent']);
          }
        }

        // 存储后端返回的全局设置（finger_type, focal_length_mm, sensor_width_mm）
        if ((apiData as any).globalSettings) {
          const gs = (apiData as any).globalSettings;
          if (gs.finger_type) sharedPointsState.fingerType = gs.finger_type;
          if (gs.focal_length_mm) sharedPointsState.focalLengthMm = gs.focal_length_mm;
          if (gs.sensor_width_mm) sharedPointsState.sensorWidthMm = gs.sensor_width_mm;
          console.log('[App] GlobalSettings:', gs);
        }

        // 3. 清理局部场景数据
        // 从每个场景对象中删除 positions 和 bezierPoints，以匹配 ThreeScene.vue 的新 props
        newScenes.forEach(scene => {
            delete scene.positions;    // 移除共享数据
            delete scene.bezierPoints; // 移除共享数据
            // 确保 backgroundPlanePosition 存在，即使为 null
           
        });

    // 如果我们之前从本地恢复过，则在刷新时优先保留本地数据，不自动用后端数据覆盖，
    // 除非调用方传入 force = true（例如用户点击“获取下一组”按钮）。
    if (haveLocalRestore && !force) {
      console.log('已从 localStorage 恢复，保留本地场景数据；跳过用后端数据自动覆盖 UI。');
      // 可选：你可能仍然希望在后台预加载后端图片，但不要替换 scenesData 或写回 localStorage
      // 因此这里直接返回，不执行后端数据的持久化覆盖。
      return;
    } else {
      // 否则使用后端返回的数据替换 UI
      scenesData.value = newScenes;
      // 自动将后端返回的完整 scenes 与共享点持久化到 localStorage，便于页面刷新回退
      try {
        const persistState: any = {
          positions: sharedPointsState.positions,
          bezierPoints: sharedPointsState.bezierPoints,
          scenes: newScenes
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(persistState));
        console.log('已将后端返回的 scenes 自动保存到 localStorage。');
      } catch (e) {
        console.warn('自动保存 scenes 到 localStorage 失败：', e);
      }
      try {
          // 合并已有 persisted 状态，保留 dataCenter / camera 等字段，避免覆盖 ThreeScene 已保存的元数据
          const existingRaw = localStorage.getItem(STORAGE_KEY);
          let existing: any = {};
          if (existingRaw) {
            try { existing = JSON.parse(existingRaw) || {}; } catch(e) { existing = {}; }
          }
          const persistState: any = {
            positions: sharedPointsState.positions,
            bezierPoints: sharedPointsState.bezierPoints,
            scenes: newScenes,
            xyRotation: sharedPointsState.xyRotation,
            aTangent: sharedPointsState.aTangent,
            // 若已有保存的 dataCenter/camera/zoom 等字段，则合并保留
            dataCenter: existing.dataCenter ?? undefined,
            cameraPosition: existing.cameraPosition ?? undefined,
            cameraQuaternion: existing.cameraQuaternion ?? undefined,
            zoomLevel: existing.zoomLevel ?? undefined,
            rollAngle: existing.rollAngle ?? undefined,
            allowBackgroundDrag: existing.allowBackgroundDrag ?? undefined,
            undoStack: existing.undoStack ?? undefined,
            redoStack: existing.redoStack ?? undefined
          };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(persistState));
          console.log('已将后端返回的 scenes 自动保存到 localStorage（并合并已有状态）。');
      } catch (e) {
          console.warn('自动保存 scenes 到 localStorage 失败：', e);
      }
    }
    // done

  } catch (error:any) {
    console.error('获取数据失败:', error);
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const persisted = JSON.parse(raw);
        if (persisted) {
          // 如果有完整 scenes 数组，使用之
          if (Array.isArray(persisted.scenes) && persisted.scenes.length > 0) {
            scenesData.value = persisted.scenes;
            // positions 也一并恢复（如果存在）
            if (Array.isArray(persisted.positions) && persisted.positions.length > 0) {
              sharedPointsState.positions = persisted.positions.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) }));
              sharedPointsState.bezierPoints = Array.isArray(persisted.bezierPoints) ? persisted.bezierPoints.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) })) : [];
            }
            // 恢复 xyRotation 和 aTangent
            if (typeof persisted.xyRotation === 'number') {
              sharedPointsState.xyRotation = persisted.xyRotation;
            }
            if (typeof persisted.aTangent === 'number') {
              sharedPointsState.aTangent = persisted.aTangent;
            }
            console.warn('后端拉取失败，已从 localStorage 回退并展示本地保存的 scenes 数据。');
            if (!haveLocalRestore) {
              errorMessage.value = '后端加载失败；已使用本地保存的数据作为回退。';
            }
            return;
          }
          // 否则尝试恢复旧式的 positions 并构造单场景回退
          if (Array.isArray(persisted.positions) && persisted.positions.length > 0) {
            sharedPointsState.positions = persisted.positions.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) }));
            sharedPointsState.bezierPoints = Array.isArray(persisted.bezierPoints) ? persisted.bezierPoints.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) })) : [];
            // 恢复 xyRotation 和 aTangent
            if (typeof persisted.xyRotation === 'number') {
              sharedPointsState.xyRotation = persisted.xyRotation;
            }
            if (typeof persisted.aTangent === 'number') {
              sharedPointsState.aTangent = persisted.aTangent;
            }
            const sceneObj: any = {
              backgroundImage: persisted.backgroundImage || '',
              cameraRotation: persisted.cameraRotation || [0,0,0],
              backgroundPlanePosition: persisted.backgroundPlanePosition || null
            };
            scenesData.value = [sceneObj];
            console.warn('后端拉取失败，已从 localStorage 回退并展示本地保存的数据。');
            if (!haveLocalRestore) {
              errorMessage.value = '后端加载失败；已使用本地保存的数据作为回退。';
            }
            return;
          }
        }
      }
    } catch (e) {
      console.warn('尝试从 localStorage 回退失败：', e);
    }

    if (!haveLocalRestore) {
      errorMessage.value = error.message || '获取数据时发生未知错误';
    } else {
      console.warn('后端拉取失败，但已存在本地恢复数据，故不展示错误消息。', error);
    }
  } finally {
    isLoading.value = false;
  }
}

// ---- 数据列表相关 ----
interface DataGroupInfo {
  groupId: string;
  imageCount: number;
  filename: string;
}

const dataList = ref<DataGroupInfo[]>([]);
const isRefreshing = ref(false);
const selectedGroupId = ref<string | null>(null);

// 获取数据列表
async function fetchDataList() {
  try {
    const response = await api.get('/api/data-list');
    if (Array.isArray(response.data)) {
      dataList.value = response.data as DataGroupInfo[];
    }
  } catch (error) {
    console.warn('[App] 获取数据列表失败:', error);
  }
}

// 点击数据列表某一行，加载该组数据
async function loadDataByGroupId(groupId: string) {
  isLoading.value = true;
  errorMessage.value = '';
  selectedGroupId.value = groupId;
  try {
    const response = await api.get('/api/data-by-id', { params: { id: groupId } });
    const apiData = response.data as ApiResponse;
    if (!apiData || !Array.isArray(apiData.images)) {
      throw new Error('返回的数据格式不正确');
    }

    const newScenes = [];
    let initialPositions: ScenePoint[] = [];
    let initialBezierPoints: ScenePoint[] = [];

    for (const imageWithMeta of apiData.images) {
      const scene = transformOutputData(apiData.outputData, imageWithMeta);
      if (newScenes.length === 0) {
        initialPositions = scene.positions || [];
        initialBezierPoints = scene.bezierPoints || [];
      }
      newScenes.push(scene);
    }

    sharedPointsState.positions = initialPositions.map(p => ({ ...p }));
    sharedPointsState.bezierPoints = initialBezierPoints.map(p => ({ ...p }));

    newScenes.forEach(scene => {
      delete scene.positions;
      delete scene.bezierPoints;
    });

    scenesData.value = newScenes;
    console.log(`[App] 已加载数据组: ${groupId}`);
  } catch (error: any) {
    errorMessage.value = error.message || '加载数据失败';
    console.error('[App] 加载数据组失败:', error);
  } finally {
    isLoading.value = false;
  }
}

// 刷新：后端重新读取文件夹并返回新列表
async function refreshDataList() {
  isRefreshing.value = true;
  errorMessage.value = '';
  try {
    const response = await api.post('/api/refresh-data');
    if (Array.isArray(response.data)) {
      dataList.value = response.data as DataGroupInfo[];
      console.log('[App] 数据列表已刷新，共', dataList.value.length, '组');
    }
  } catch (error: any) {
    errorMessage.value = error.message || '刷新失败';
    console.error('[App] 刷新数据失败:', error);
  } finally {
    isRefreshing.value = false;
  }
}

// 可选的预加载函数
function preloadImages(urls: string[]) {
  const promises = urls.map((url: string) => {
    return new Promise((resolve, reject) => {
      const img = new Image()
      img.src = url
      img.onload = resolve
      img.onerror = reject
    })
  })
  return Promise.all(promises)
}

// 页面挂载时自动获取图片
onMounted(() => {
  // 直接初始化操作管理器（无需登录）
  initOperationManager('default_token').then(() => {
    console.log('[App] 操作管理器初始化完成');
  });

  // 优先尝试加载本地持久化的场景状态，避免刷新时被后端覆盖
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const persisted = JSON.parse(raw);
      // 如果本地存在完整的 scenes 数组或至少存在 positions，则恢复并跳过自动拉取后端
      if (persisted) {
        const hasScenes = Array.isArray(persisted.scenes) && persisted.scenes.length > 0;
        const hasPositions = Array.isArray(persisted.positions) && persisted.positions.length > 0;
        if (hasScenes || hasPositions) {
          if (hasPositions) {
            sharedPointsState.positions = persisted.positions.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) }));
            sharedPointsState.bezierPoints = Array.isArray(persisted.bezierPoints) ? persisted.bezierPoints.map((p: any) => ({ name: p.name, x: Number(p.x), y: Number(p.y), z: Number(p.z) })) : [];
          }
          // 恢复 xyRotation 和 aTangent 参数（避免刷新后重置为默认值）
          if (typeof persisted.xyRotation === 'number') {
            sharedPointsState.xyRotation = persisted.xyRotation;
          }
          if (typeof persisted.aTangent === 'number') {
            sharedPointsState.aTangent = persisted.aTangent;
          }
          if (hasScenes) {
            scenesData.value = persisted.scenes;
          } else {
            // 构造一个场景数据用于 SidePanel 和 ThreeScene（兼容旧格式）
            const sceneObj: any = {
              backgroundImage: persisted.backgroundImage || '',
              cameraRotation: persisted.cameraRotation || [0,0,0],
              backgroundPlanePosition: persisted.backgroundPlanePosition || null
            };
            scenesData.value = [sceneObj];
          }
          haveLocalRestore = true;
          console.log('已从 localStorage 恢复场景与共享点（含 xyRotation/aTangent）；不再调用后端获取参数。');
        }
      }
    }
  } catch (e) {
    console.warn('尝试从 localStorage 恢复失败，继续从后端拉取数据', e);
  }
  // 如果未能从 localStorage 恢复数据，则从后端拉取
  // 说明：如果已有本地恢复（haveLocalRestore），则不在页面刷新时自动拉取后端数据，
  // 只有用户点击"获取下一组"按钮时才会触发 `fetchNextDataBatch()`。
  // 同时，只有在已登录的情况下才会自动拉取后端数据
  if (!haveLocalRestore) {
    fetchNextDataBatch();
  } else {
    // 已从 localStorage 恢复完整数据，用不消耗数据组的接口同步最新参数
    console.log('检测到本地恢复，跳过页面挂载时的自动后端拉取，仅同步参数。');
    fetchAndUpdateParams();
  }

  // 挂载时拉取数据列表（不依赖登录）
  fetchDataList();
})

const triggerFileUpload = () => {
  // 重置状态
  message.value = '';
  uploadProgress.value = 0;
  fileName.value = '';
  
  // 以编程方式点击隐藏的文件输入框，从而打开文件选择对话框
  if (fileInputRef.value)
  fileInputRef.value.click();
};

// 2. 当用户在文件选择框中选择了文件后，这个函数被调用
const handleFileSelected = (event:any) => {
  const files = event.target.files;
  if (files.length > 0) {
    const file = files[0]; // 这就是我们需要的 fileObject
    fileName.value = file.name;

    // 立即调用上传函数
    uploadVideo(file);
  }
};

// 3. 这是你提供的上传函数，现在它被无缝集成进来
const uploadVideo = async (fileObject:any) => {
  isLoading.value = true;
  
  // 创建一个 FormData 实例
  const formData = new FormData();

  // 将文件附加到 FormData 中
  // 第一个参数 'video' 必须和后端 r.FormFile("video") 中的名字一致
  formData.append('video', fileObject);

  // 将其他附带数据也附加到 FormData 中
  formData.append('userId', userId);
  formData.append('source', 'WEB');

  try {
    // 使用 Axios 发送 formData 对象
    console.log('即将使用的 Axios 实例的默认配置:', api_vedio.defaults);
    const response = await api_vedio.post('/api/upload', formData, {
      // 添加上传进度监听器
      onUploadProgress: (progressEvent) => {
        if (!progressEvent.total) return;
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        uploadProgress.value = percentCompleted;
      }
    });
    
    message.value = '上传成功!';
    console.log('上传成功:', response.data);

  } catch (error) {
    message.value = '上传失败，请查看控制台获取详情。';
    console.error('上传失败:', error);
  } finally {
    isLoading.value = false;
  }
}

// <h3>注册信息</h3>
//     <input v-model="register_data[0].username" placeholder="用户名" />
//     <input v-model="register_data[0].password" type="password" placeholder="密码" />
//     <button @click="test_register(register_data[0].username, register_data[0].password)">注册</button>
//     <p v-if="register_data[0].error">{{ register_data[0].error }}</p>

</script>
<template>
  <div class="main-layout">
    <div class="auth-sidebar">
      <div class="data-section">
        <div class="data-header">
          <h3>管理区</h3>
          <button class="refresh-btn" @click="refreshDataList" :disabled="isRefreshing">
            {{ isRefreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        <div class="data-list" v-if="dataList.length > 0">
          <div
            v-for="item in dataList"
            :key="item.groupId"
            class="data-list-item"
            :class="{ active: selectedGroupId === item.groupId }"
            @click="loadDataByGroupId(item.groupId)"
          >
            <span class="item-id">{{ item.groupId }}</span>
            <span class="item-meta">{{ item.filename || item.groupId }} ({{ item.imageCount }}张)</span>
          </div>
        </div>
        <div v-else-if="isLoading" class="list-loading">加载中...</div>
        <div v-else class="list-empty">暂无数据</div>
      </div>
    </div>

    <div class="main-content">
      <SidePanel
        v-if="scenesData.length > 0"
        :scenesData="scenesData"
        :onSave="saveAllPointsData"
        :isSaving="isSaving"
        :onFetchNext="() => fetchNextDataBatch(true)"
        :onUploadResult="Save_Building_Result"
      />
      <div v-else-if="isLoading" class="loading">场景加载中...</div>
    </div>
  </div>
</template>

<style scoped>
:deep(#app), 
#app {
  display: block;      /* 覆盖默认的 grid 布局 */
  max-width: none;     /* 去掉最大宽度限制 */
  margin: 0;           /* 去掉自动边距 */
  padding: 0;          /* 去掉内边距 */
  width: 100vw;
  height: 100vh;
}
.main-layout {
  display: flex;
  flex-direction: row; /* 水平排列 */
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* 左侧栏：压缩空间 */
.auth-sidebar {
  flex: 0 0 220px;
  background: #f8f9fa;
  border-right: 1px solid #ddd;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 10;
  overflow: hidden;
}

/* 右侧内容区：扩张空间 */
.main-content {
  flex: 1;
  height: 100%;
  position: relative;
}

/* 数据区整体 */
.data-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.data-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.data-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.refresh-btn {
  padding: 4px 10px;
  font-size: 12px;
  background: #17a2b8;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.refresh-btn:hover:not(:disabled) { background: #138496; }
.refresh-btn:disabled { background: #ccc; cursor: not-allowed; }

/* 数据列表 */
.data-list {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
}

.data-list-item {
  padding: 8px 10px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 2px;
  transition: background 0.15s;
}
.data-list-item:last-child { border-bottom: none; }
.data-list-item:hover { background: #e9f5ff; }
.data-list-item.active { background: #cce5ff; }

.item-id {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}
.item-meta {
  font-size: 11px;
  color: #666;
}

.list-loading, .list-empty {
  padding: 12px;
  font-size: 12px;
  color: #888;
  text-align: center;
}

.error {
  font-size: 11px;
  color: #dc3545;
  margin: 4px 0;
}
</style>
