<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { DragControls } from 'three/examples/jsm/controls/DragControls.js'
import { type ScenePoint } from '../stores/sharedStore.ts'

const props = defineProps<{
  tipSidePoints: ScenePoint[]
}>()

const emit = defineEmits<{
  pointUpdate: [pointName: string, newPosition: THREE.Vector3]
}>()

// 撤销历史栈：每条记录为各点位置的快照
const undoHistory = ref<Array<{ pointName: string; x: number; y: number; z: number }[]>>([])

function canUndo() {
  return undoHistory.value.length > 0
}

function undoLastDrag() {
  if (undoHistory.value.length === 0) return
  const snapshot = undoHistory.value.pop()!
  snapshot.forEach(({ pointName, x, y, z }) => {
    emit('pointUpdate', pointName, new THREE.Vector3(x, y, z))
  })
}

const containerRef = ref<HTMLElement | null>(null)
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let dragControls: DragControls | null = null

const draggableObjects: THREE.Mesh[] = []
const pointLabels: THREE.Sprite[] = []
const pointMeshes: THREE.Mesh[] = []
let tipProfileCurve: THREE.Line | null = null
let baseLine: THREE.Line | null = null

onMounted(() => {
  initScene()
  animate()
})

function initScene() {
  if (!containerRef.value) return

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf0f0f0)

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight
  camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 1000)
  // 摄像机垂直对准 D 点截面（沿 +Z 轴方向正交俯视 XY 平面）
  // 截面中心约为 (0, -0.6)，相机沿 Z 轴退后 12 单位
  camera.position.set(0, 0, 28)
  camera.up.set(0, 1, 0)
  camera.lookAt(0, 0, 0)

  try {
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      failIfMajorPerformanceCaveat: false,
      powerPreference: 'high-performance',
    })
  } catch (e) {
    console.error('WebGL 创建失败:', e)
    containerRef.value.innerHTML = '<div style="color:#333;padding:20px;background:#f0f0f0;height:100%;display:flex;align-items:center;justify-content:center;"><p>WebGL 不可用，请检查：<br>1. 确保浏览器已开启硬件加速<br>2. 关闭其他标签页释放 WebGL 上下文<br>3. 尝试使用 Chrome / Edge 最新版</p></div>'
    return
  }
  renderer.setSize(width, height)
  containerRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 0)
  controls.enabled = false  // 禁用所有相机拖拽/旋转/缩放，保持视角固定

  // 不添加坐标轴和网格，保持截面视图简洁

  updateTipProfile()
  setupDragControls()

  window.addEventListener('resize', onWindowResize)
}

function updateTipProfile() {
  if (!scene) return

  const sceneRef = scene

  pointMeshes.forEach(obj => sceneRef.remove(obj))
  draggableObjects.forEach(obj => sceneRef.remove(obj))
  pointLabels.forEach(label => sceneRef.remove(label))
  if (tipProfileCurve) {
    sceneRef.remove(tipProfileCurve)
    if (tipProfileCurve.geometry) tipProfileCurve.geometry.dispose()
    if (tipProfileCurve.material instanceof THREE.Material) tipProfileCurve.material.dispose()
    tipProfileCurve = null
  }
  if (baseLine) {
    sceneRef.remove(baseLine)
    if (baseLine.geometry) baseLine.geometry.dispose()
    if (baseLine.material instanceof THREE.Material) baseLine.material.dispose()
    baseLine = null
  }
  pointMeshes.length = 0
  draggableObjects.length = 0
  pointLabels.length = 0

  const pointNames = ['I', 'J', 'D_P1_I', 'D_P1_J', 'D']

  // 每个点的标签偏移量，使标签向各自所在方向散开避免重叠
  const labelOffsets: Record<string, { dx: number; dy: number }> = {
    'I':      { dx:  2.0, dy: -1.5 }, // 右下
    'J':      { dx: -2.0, dy: -1.5 }, // 左下
    'D_P1_I': { dx:  2.0, dy:  1.5 }, // 右上
    'D_P1_J': { dx: -2.0, dy:  1.5 }, // 左上
    'D':      { dx:  0.0, dy:  1.8 }, // 正上方
  }

  pointNames.forEach(pointName => {
    const pointData = props.tipSidePoints.find(p => p.name === pointName)
    if (!pointData) return

    const geometry = new THREE.SphereGeometry(0.5, 32, 32)
    const material = new THREE.MeshBasicMaterial({
      color: pointName === 'D' ? 0xff0000 : 0xff00ff
    })
    const sphere = new THREE.Mesh(geometry, material)
    sphere.position.set(pointData.x, pointData.y, pointData.z)
    sphere.userData.pointName = pointName
    const off = labelOffsets[pointName] ?? { dx: 0, dy: 1.2 }
    sphere.userData.labelOffsetX = off.dx
    sphere.userData.labelOffsetY = off.dy

    sceneRef.add(sphere)
    pointMeshes.push(sphere)
    
    if (pointName !== 'A' && pointName !== 'D') {
      // A 点和 D 点不参与拖拽，保持固定
       draggableObjects.push(sphere)
    }

    const label = createTextLabel(pointName)
    label.position.set(pointData.x + off.dx, pointData.y + off.dy, pointData.z)
    sceneRef.add(label)
    pointLabels.push(label)
  })

  createJDICurve()
  createBaseLine()  // 添加基线
}

function createJDICurve() {
  if (!scene) return

  const J = props.tipSidePoints.find(p => p.name === 'J')
  const D_P1_J = props.tipSidePoints.find(p => p.name === 'D_P1_J')
  const D = props.tipSidePoints.find(p => p.name === 'D')
  const D_P1_I = props.tipSidePoints.find(p => p.name === 'D_P1_I')
  const I = props.tipSidePoints.find(p => p.name === 'I')

  if (!J || !D_P1_J || !D || !D_P1_I || !I) return

  const curve1 = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(J.x, J.y, J.z),
    new THREE.Vector3(D_P1_J.x, D_P1_J.y, D_P1_J.z),
    new THREE.Vector3(D.x, D.y, D.z)
  )
  const curve2 = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(D.x, D.y, D.z),
    new THREE.Vector3(D_P1_I.x, D_P1_I.y, D_P1_I.z),
    new THREE.Vector3(I.x, I.y, I.z)
  )

  const points = [...curve1.getPoints(25), ...curve2.getPoints(25)]
  const geometry = new THREE.BufferGeometry().setFromPoints(points)
  const material = new THREE.LineBasicMaterial({ color: 0xff00ff, linewidth: 2 })
  tipProfileCurve = new THREE.Line(geometry, material)

  scene.add(tipProfileCurve)
}

function createBaseLine() {
  if (!scene) return

  const I = props.tipSidePoints.find(p => p.name === 'I')
  const J = props.tipSidePoints.find(p => p.name === 'J')
  const D = props.tipSidePoints.find(p => p.name === 'D')

  if (!I || !J || !D) return

  // 创建从I到D到J的基线
  const basePoints = [
    new THREE.Vector3(I.x, I.y, I.z),
    new THREE.Vector3(D.x, D.y, D.z),
    new THREE.Vector3(J.x, J.y, J.z)
  ]

  const geometry = new THREE.BufferGeometry().setFromPoints(basePoints)
  const material = new THREE.LineDashedMaterial({
    color: 0x666666,
    linewidth: 1,
    dashSize: 0.3,
    gapSize: 0.2,
    scale: 1
  })
  baseLine = new THREE.Line(geometry, material)
  baseLine.computeLineDistances()  // 必须调用这个方法来显示虚线
  scene.add(baseLine)
}

function createTextLabel(text: string): THREE.Sprite {
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')!
  canvas.width = 256
  canvas.height = 128

  context.fillStyle = 'rgba(0, 0, 0, 0)'
  context.fillRect(0, 0, canvas.width, canvas.height)

  context.font = 'Bold 48px Arial'
  context.fillStyle = 'black'
  context.textAlign = 'center'
  context.fillText(text, 128, 64)

  const texture = new THREE.CanvasTexture(canvas)
  const spriteMaterial = new THREE.SpriteMaterial({ map: texture })
  const sprite = new THREE.Sprite(spriteMaterial)
  sprite.scale.set(8, 4, 1)

  return sprite
}

function setupDragControls() {
  if (!scene || !camera || !renderer) return

  dragControls = new DragControls(draggableObjects, camera, renderer.domElement)

  dragControls.addEventListener('dragstart', () => {
    // 相机已固定（controls.enabled = false），无需在此禁用
    // 记录拖拽前的所有点位置快照
    const snapshot = props.tipSidePoints.map(p => ({ pointName: p.name, x: p.x, y: p.y, z: p.z }))
    undoHistory.value.push(snapshot)
  })

  dragControls.addEventListener('drag', (event) => {
    const object = event.object as THREE.Mesh
    const pointName = object.userData.pointName

    // D_P1_J / D_P1_I 只能横向拖动，锁死 Y
    if (pointName === 'D_P1_J' || pointName === 'D_P1_I') {
      const origY = props.tipSidePoints.find(p => p.name === pointName)?.y ?? 0
      object.position.y = origY
    }

    const labelIndex = draggableObjects.indexOf(object)
    if (pointLabels[labelIndex]) {
      const ox = object.userData.labelOffsetX ?? 0
      const oy = object.userData.labelOffsetY ?? 1.2
      pointLabels[labelIndex].position.set(
        object.position.x + ox,
        object.position.y + oy,
        object.position.z
      )
    }

    emit('pointUpdate', pointName, object.position.clone())

    if (tipProfileCurve && scene) {
      scene.remove(tipProfileCurve)
      createJDICurve()
    }
    
    if (baseLine && scene) {
      scene.remove(baseLine)
      createBaseLine()
    }
  })

  dragControls.addEventListener('dragend', () => {
    // 相机已固定，无需恢复 controls.enabled
  })
}

function onWindowResize() {
  if (!containerRef.value || !camera || !renderer) return

  const width = containerRef.value.clientWidth
  const height = containerRef.value.clientHeight

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate() {
  requestAnimationFrame(animate)

  if (controls) controls.update()
  if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }
}

watch(() => props.tipSidePoints, () => {
  updateTipProfile()
}, { deep: true })

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
  
  if (dragControls) {
    dragControls.dispose()
  }
  
  if (controls) {
    controls.dispose()
  }
  
  if (renderer) {
    renderer.dispose()
  }
  
  draggableObjects.forEach(obj => {
    obj.geometry.dispose()
    if (obj.material instanceof THREE.Material) {
      obj.material.dispose()
    }
  })
  
  pointLabels.forEach(label => {
    if (label.material instanceof THREE.Material) {
      label.material.dispose()
    }
    if (label.material.map) {
      label.material.map.dispose()
    }
  })
  
  if (tipProfileCurve) {
    if (tipProfileCurve.geometry) tipProfileCurve.geometry.dispose()
    if (tipProfileCurve.material instanceof THREE.Material) {
      tipProfileCurve.material.dispose()
    }
  }
  
  if (baseLine) {
    if (baseLine.geometry) baseLine.geometry.dispose()
    if (baseLine.material instanceof THREE.Material) {
      baseLine.material.dispose()
    }
  }
})
</script>

<template>
  <div class="tip-side-profile-container">
    <div class="profile-header">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h3>尖侧轮廓 (Tip Side Profile: I-J)</h3>
        <button @click="undoLastDrag" :disabled="!canUndo()" style="font-size:12px; padding:4px 10px;">撤销</button>
      </div>
      <p class="profile-description">拖拽控制点调整指甲尖部拱形 • 紫色曲线为轮廓线 • 灰色虚线为基线</p>
    </div>
    <div ref="containerRef" class="canvas-container"></div>
  </div>
</template>

<style scoped>
.tip-side-profile-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.profile-header {
  margin-bottom: 10px;
}

h3 {
  margin: 0 0 5px 0;
  font-size: 16px;
  color: #2c3e50;
  font-weight: 600;
}

.profile-description {
  margin: 0;
  font-size: 12px;
  color: #7f8c8d;
  line-height: 1.4;
}

.canvas-container {
  flex: 1;
  min-height: 0;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  background: #ffffff;
  overflow: hidden;
}

.canvas-container:hover {
  border-color: #9b59b6;
}
</style>
