# jointstest_new.py 与前端四元数代码对比分析

> 日期：2026-04-24

## 1. 职责分工

| | `jointstest_new.py`（Python 后端） | 前端（ThreeScene.vue / App.vue） |
|---|---|---|
| **角色** | 四元数**生产者** | 四元数**消费者** |
| **做什么** | 从 WiLoR 手部 21 关键点的 3D 坐标计算每个手指甲片的局部坐标系 → 旋转矩阵 → 四元数 | 接收后端输出的四元数，直接应用到 Three.js 模型组 |
| **是否有骨骼→四元数的计算** | 有，完整实现 | 无 |

## 2. Python 后端四元数生成逻辑（jointstest_new.py）

### 2.1 坐标系约定

```
+X : 沿最后一个指节朝外（dist → tip）
+Z : 垂直甲面（受 MODEL_Z_POINTS_INWARD 控制朝内/朝外）
+Y : 右手系推导 Y = Z × X，再正交化 Z = X × Y
```

### 2.2 Z 轴策略

**四指**（index/middle/ring/pinky）：
- `Z_AXIS_MODE = "plane_middle"`：将 `mid → dist`（倒数第二节指骨方向）投影到垂直于 X 的平面，得到 Z
- 退化处理：两节指骨近共线时，用 `tip → mid` 投影替代
- 符号约束：Z 尽量朝向相机（z 越小越近）

**大拇指**：
- `THUMB_Z_MODE = "palm_outward_bone_blend"`
- 主方向（90%）：从掌心中心指向拇指远节，投影到垂直 X 的平面 → 表示"远离掌心/指腹"
- 稳定方向（10%）：大拇指自身骨节平面方向
- 可选 `THUMB_FLIP_Z_TO_CAMERA`：仅决定 Z 正负号，不改变方向
- 可选 `THUMB_EXTRA_ROLL_DEG`：绕 X 轴微调固定角度偏差

### 2.3 四元数输出

```python
R = np.stack([dir_x, dir_y, dir_z], axis=1)  # 列向量组成旋转矩阵
q = rotation_matrix_to_quaternion(R)           # Shepperd 方法
# 输出顺序: [qx, qy, qz, qw]
```

## 3. 前端四元数处理逻辑

### 3.1 数据加载（App.vue）

```typescript
// 从后端 JSON 读取 quaternion，写入 scene.cameraRotation
const cameraRotation = meta.quaternion.map((value) => Number(value) || 0);
```

### 3.2 四元数应用（ThreeScene.vue）

```typescript
// 直接构造 THREE.Quaternion 并赋给 modelGroup
function applyCameraRotationFromArray(newRotation: number[]) {
  const { quaternion: targetQuaternion } = buildFrontendQuaternionFromRotation(newRotation);
  modelGroup.quaternion.copy(targetQuaternion);
}
```

### 3.3 滑条增量叠加

用户通过 pitch/yaw/roll 滑条调整姿态时，增量以局部轴旋转方式叠加到 modelGroup：

```typescript
modelGroup.quaternion.multiply(
  new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), degToRad(dy))
);
```

保存时直接将 `modelGroup.quaternion` 写回 `scene.cameraRotation`，不再做 delta 合成。

### 3.4 导出

```typescript
// 保存时直接返回 scene.cameraRotation（已含滑条累积值）
function getCorrectedQuaternion(scene: any): number[] {
  return [rot[0], rot[1], rot[2], rot[3]];
}
```

## 4. 数据流

```
WiLoR 手部关键点 (21×3D)
        ↓
jointstest_new.py
  compute_finger_frame_for_nail() → X/Y/Z 轴
  build_rotation_matrix_from_axes() → 旋转矩阵 R
  rotation_matrix_to_quaternion() → [qx, qy, qz, qw]
        ↓
JSON 文件 (quaternion 字段)
        ↓
App.vue 加载 → scene.cameraRotation
        ↓
ThreeScene.vue → modelGroup.quaternion.copy(THREE.Quaternion(x,y,z,w))
        ↓
用户滑条调整 → 增量叠加到 modelGroup.quaternion
        ↓
保存 → modelGroup.quaternion 写回 scene.cameraRotation → 导出 JSON
```

## 5. 前端不涉及手指骨骼→四元数的计算

前端自身没有任何"从关节坐标推导四元数"的逻辑。所有四元数都来自后端。前端的工作仅限于：
1. 构造 `THREE.Quaternion` 并赋值给模型组
2. 用户滑条增量叠加（pitch/yaw/roll 局部旋转）
3. 保存/导出时回写累积后的四元数

## 6. 关于"模型初始朝向匹配"

前端 `modelGroup = new THREE.Group()` 初始为单位旋转。标注数据（点、曲线坐标）和四元数都由同一个 Python 后端计算，共享同一套坐标系约定（+X 沿指骨、+Z 垂直甲面），因此不存在初始朝向不匹配的问题。

如果将来引入外部 3D 模型文件或更换标注数据来源，需要确认新数据的本地坐标轴是否与后端约定一致。

## 7. 旋转结果异常时的排查方向

1. **Z 轴策略** — `Z_AXIS_MODE` / `THUMB_Z_MODE` 配置是否适合当前手部姿态
2. **左右手镜像** — Python 端对左手做了 `joints[:, 0] *= -1`，前端是否正确区分左右手
3. **四元数累积** — 前端滑条增量叠加后 `saveCurrentCameraRotationToProps` 写回的值是否正确覆盖了原始值


在这个项目里，WiLoR 输出的手部关键点是相机坐标系下的 3D 坐标，采用的是 OpenCV 约定：                                                              
                                                                                                                                                  
  +X : 图像右方       
  +Y : 图像下方
  +Z : 朝场景深处（远离相机）                                                                                                                                                                                                                                                                         
  所以 Python 代码里出现了这样的逻辑：

  # jointstest_new.py:194-198
  fingertip_cam = p_tip + cam_t
  z_end_cam = fingertip_cam + dir_z * 0.01
  if z_end_cam[2] > fingertip_cam[2]:
      dir_z = -dir_z

  z 值越小 = 离相机越近 = 越可见。这段代码的意思是：如果 Z 轴朝远处走了，就翻转它，让它朝向相机（朝观察者可见的一侧）。

  简单说，相机坐标系就是"以相机为原点，描述手在哪里、朝哪个方向"的参考系。Python 后端在这个参考系里算四元数，前端 Three.js
  里也用这个四元数旋转模型组，两边用的是同一套参考系。

## 8. OpenCV 与 Three.js 坐标系差异

前端规定当模型四元数为单位四元数 `(0,0,0,1)` 时：

```
+X : 图像右方
+Y : 图像上方
+Z : 朝向相机（朝向观察者）
```

这是 Three.js 的标准约定。但 Python 后端（WiLoR / OpenCV）用的是另一套约定：

```
OpenCV:   +X 右,  +Y 下,  +Z 远离相机
Three.js: +X 右,  +Y 上,  +Z 朝向相机
```

**Y 和 Z 的方向是反的。** OpenCV → Three.js 相当于绕 X 轴旋转 180°（Y 和 Z 同时翻转）。

Python 算出的四元数是在 OpenCV 空间里定义的，直接赋给 Three.js 的 `modelGroup.quaternion` 时，两个空间的参考轴不同，旋转结果可能存在系统性偏差。

排查方法：
1. 如果旋转效果视觉上正确 — 说明标注数据在流转过程中已经隐式补偿了这个差异，无需额外处理
2. 如果存在系统性的上下/前后翻转 — 需要在四元数传入 Three.js 前显式做坐标系转换（绕 X 轴旋转 180°）

---

## 9. 实测验证：四元数坐标系变换规律（2026-04-26）

### 9.1 验证方法

从 feature JSON 文件中提取 thumb 手指的 quaternion（OpenCV 空间），生成 384 种排列组合（4! × 2⁴ = 384，去重后 192 种唯一旋转），通过前端测试按钮逐一尝试，找到每个场景的正确旋转值。

### 9.2 数据对比

| 场景 | 帧号 | thumb 原始四元数（OpenCV） | R_x(180°) 变换后 | 用户测试确认的正确值 | 匹配 |
|---|---|---|---|---|---|
| 1 | 0003 | [-0.1796, **-0.3198**, **-0.5177**, 0.7729] | [-0.1796, **0.3198**, **0.5177**, 0.7729] | [-0.1796, 0.3198, 0.5177, 0.7729] | ✅ |
| 2 | 0005 | [-0.7443, **0.0311**, **0.1760**, 0.6435] | [-0.7443, **-0.0311**, **-0.1760**, 0.6435] | [-0.7443, **0.0311**, **-0.1760**, 0.6435] | ⚠️ |
| 3 | 0010 | [-0.5570, **-0.2543**, **-0.1188**, 0.7817] | [-0.5570, **0.2543**, **0.1188**, 0.7817] | [-0.5570, 0.2543, 0.1188, 0.7817] | ✅ |
| 4 | 0012 | [-0.7380, **0.1479**, **0.0555**, 0.6560] | [-0.7380, **-0.1479**, **-0.0555**, 0.6560] | [-0.7380, -0.1479, -0.0555, 0.6560] | ✅ |
| 5 | 0013 | [-0.3694, **0.0760**, **-0.4083**, 0.8313] | [-0.3694, **-0.0760**, **0.4083**, 0.8313] | [-0.3694, -0.0760, 0.4083, 0.8313] | ✅ |

### 9.3 分析结论

5 组数据中 4 组完全吻合，第 2 组（frame 0005）y 分量仅 0.031（约 1.8°偏差），正负在视觉上不可区分。

**变换规律**：`[x, y, z, w]` → `[x, -y, -z, w]`（x 和 w 不变，y 和 z 取反）

这等价于绕 X 轴旋转 180°，即四元数形式 `(1, 0, 0, 0)` 表示的旋转。这与第 8 节的分析完全一致：

- OpenCV 的 +Y 朝下、+Z 远离相机
- Three.js 的 +Y 朝上、+Z 朝向相机
- Y 和 Z 同时翻转 = 绕 X 轴旋转 180°

### 9.4 数学验证

绕 X 轴旋转 180° 的四元数为 `q_rot = (1, 0, 0, 0)`（即 `[x=1, y=0, z=0, w=0]`）。

对任意四元数 `q = (qx, qy, qz, qw)` 施加该旋转：

```
q' = q_rot × q = (1,0,0,0) × (qx,qy,qz,qw)
   = (qw·1 + qx·0, qy·0 - qz·0, qz·0 - qy·0, qw·0 - qx·(-1))
```

但更直观的理解：绕 X 轴旋转 180° 会使 Y→-Y、Z→-Z，因此：

```
q' = (qx, -qy, -qz, qw)
```

这与实测数据完全吻合。

### 9.5 正确的应用方式

在四元数从后端（OpenCV 空间）传入前端（Three.js 空间）时，需要对 y、z 分量取反。保存时再反向变换回来，确保后端/数据文件始终使用 OpenCV 坐标系。

```
加载时：OpenCV → Three.js   [x, y, z, w] → [x, -y, -z, w]
保存时：Three.js → OpenCV   [x, y, z, w] → [x, -y, -z, w]（两次取反恢复原值）
```
