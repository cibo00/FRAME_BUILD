# localStorage 数据保存功能更新说明

## 更新内容

已为前端添加了完整的 localStorage 数据保存功能，确保 ThreeScene.vue 中的所有关键数据都能保存到后端。

## 新增保存的数据

除了之前保存的基本数据（positions、bezierPoints、scenes、globalADArc）外，现在还会保存以下 localStorage 数据：

### 1. 主状态数据 (mainState)
**键名**: `frame_build_three_scene_state_v1`

**包含内容**:
- positions: 点位置数据
- bezierPoints: 贝塞尔点数据
- backgroundImage: 背景图片URL
- backgroundPlanePosition: 背景平面位置
- cameraRotation: 相机旋转角度
- zoomLevel: 缩放级别
- rollAngle: 滚动角度
- imageScale: 图片缩放比例
- dataCenter: 数据中心位置
- allowBackgroundDrag: 是否允许拖动背景
- undoStack: 撤销栈
- redoStack: 重做栈
- cameraPosition: 相机位置
- cameraQuaternion: 相机四元数
- scenes: 场景元数据数组

### 2. 原始相机旋转映射 (originalRotationMap)
**键名**: `frame_build_three_scene_state_v1_original_camera_rotation_map`

**用途**: 存储后端原始视角的独立键（按场景存储为映射）

**数据结构**:
```json
{
  "scene_key_1": [pitch, roll, yaw],
  "scene_key_2": [pitch, roll, yaw],
  ...
}
```

### 3. 全局 AD_arc 值 (globalAdArcValue)
**键名**: `frame_build_three_scene_state_v1_global_adarc`

**用途**: 全局存储 AD_arc 的键（统一在所有场景中同步）

**数据类型**: 字符串（数字的字符串表示）

### 4. 原始 AD_arc 映射 (originalAdArcMap)
**键名**: `frame_build_three_scene_state_v1_original_adarc_map`

**用途**: 存储后端原始 AD_arc 的映射（按场景 key 存储原始值，reset 读取它）

**数据结构**:
```json
{
  "scene_key_1": 0.123,
  "scene_key_2": 0.456,
  ...
}
```

### 5. 相机增量映射 (cameraDeltaMap)
**键名**: `frame_build_three_scene_state_v1_camera_delta_map`

**用途**: 存储每个场景的滑条增量映射（按场景 key 存储）

**数据结构**:
```json
{
  "scene_key_1": {
    "pitchDelta": 0,
    "rollDelta": 0,
    "yawDelta": 0
  },
  "scene_key_2": {
    "pitchDelta": 5,
    "rollDelta": -3,
    "yawDelta": 2
  },
  ...
}
```

## 实现机制

### 1. 自动保存机制

#### 方式一：Vue Watch 监听
监听共享点数据（positions、bezierPoints、scenesData）的变化，自动触发保存。

```typescript
watch(
  () => [sharedPointsState.positions, sharedPointsState.bezierPoints, scenesData.value],
  () => {
    saveAllDataToBackend();
  },
  { deep: true }
);
```

#### 方式二：localStorage 定期检查
每2秒检查一次 localStorage 的变化，如果检测到变化则触发保存（带1秒防抖）。

```typescript
setInterval(() => {
  if (operationManager) {
    const currentData = JSON.stringify({
      mainState: getLocalStorageItem('frame_build_three_scene_state_v1'),
      originalRotationMap: getLocalStorageItem('...'),
      // ... 其他数据
    });

    if (currentData !== lastSavedData) {
      lastSavedData = currentData;
      debouncedSave(); // 1秒防抖
    }
  }
}, 2000);
```

#### 方式三：跨标签页监听
监听 `storage` 事件，当其他标签页修改 localStorage 时也能检测到。

```typescript
window.addEventListener('storage', (e: StorageEvent) => {
  if (e.key && e.key.startsWith('frame_build_three_scene_state')) {
    debouncedSave();
  }
});
```

### 2. 数据恢复机制

登录后初始化操作管理器时，自动从后端恢复所有保存的数据：

```typescript
async function initOperationManager(token: string) {
  // 创建操作管理器
  operationManager = new OperationManager(token);

  // 恢复临时操作
  const savedData = await operationManager.init();

  if (savedData) {
    // 恢复共享点数据
    sharedPointsState.positions = savedData.positions;
    sharedPointsState.bezierPoints = savedData.bezierPoints;
    scenesData.value = savedData.scenes;

    // 恢复 localStorage 数据
    setLocalStorageItem('frame_build_three_scene_state_v1', savedData.mainState);
    setLocalStorageItem('...', savedData.originalRotationMap);
    // ... 恢复其他数据
  }

  // 启动 localStorage 监听器
  setupLocalStorageListener();
}
```

## 辅助函数

### getLocalStorageItem(key: string)
从 localStorage 读取数据，自动处理 JSON 解析。

```typescript
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
```

### setLocalStorageItem(key: string, value: any)
设置 localStorage 数据，自动处理 JSON 序列化。

```typescript
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
```

### saveAllDataToBackend()
收集所有数据并保存到后端。

```typescript
function saveAllDataToBackend() {
  if (!operationManager) return;

  const operationData = {
    // 共享点数据
    positions: sharedPointsState.positions,
    bezierPoints: sharedPointsState.bezierPoints,
    scenes: scenesData.value,
    globalADArc: (sharedPointsState as any).globalAdArc,

    // localStorage 数据
    mainState: getLocalStorageItem('frame_build_three_scene_state_v1'),
    originalRotationMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_camera_rotation_map'),
    globalAdArcValue: getLocalStorageItem('frame_build_three_scene_state_v1_global_adarc'),
    originalAdArcMap: getLocalStorageItem('frame_build_three_scene_state_v1_original_adarc_map'),
    cameraDeltaMap: getLocalStorageItem('frame_build_three_scene_state_v1_camera_delta_map'),

    timestamp: Date.now()
  };

  operationManager.saveTempOperation(operationData);
}
```

## 防抖和节流

### 保存防抖
- Vue Watch 触发的保存：使用 OperationManager 内置的 500ms 防抖
- localStorage 检查触发的保存：使用 1秒防抖

### 检查节流
- localStorage 定期检查：每2秒检查一次

## 数据流程

### 保存流程
```
用户操作
  ↓
数据变化（positions/bezierPoints/scenes 或 localStorage）
  ↓
触发保存（Vue Watch 或定期检查）
  ↓
收集所有数据（共享点 + localStorage）
  ↓
防抖处理（500ms 或 1秒）
  ↓
发送到后端 API (/api/temp-operation/save)
  ↓
保存到数据库
```

### 恢复流程
```
用户登录
  ↓
初始化 OperationManager
  ↓
从后端获取临时操作 (/api/temp-operation/get)
  ↓
恢复共享点数据（positions/bezierPoints/scenes）
  ↓
恢复 localStorage 数据（5个键）
  ↓
启动 localStorage 监听器
  ↓
应用恢复到之前的状态
```

## 测试建议

### 1. 基本保存测试
1. 登录系统
2. 拖动点位置
3. 调整相机视角（使用滑条）
4. 修改 AD_arc 值
5. 等待2-3秒（确保保存完成）
6. 在浏览器开发者工具 → Network 标签中查看是否发送了 `/api/temp-operation/save` 请求

### 2. 恢复测试
1. 完成上述操作后
2. 刷新页面
3. 检查点位置是否恢复
4. 检查相机视角是否恢复
5. 检查 AD_arc 值是否恢复
6. 打开浏览器开发者工具 → Application → Local Storage，查看是否恢复了所有键值

### 3. localStorage 变化测试
1. 登录系统
2. 打开浏览器开发者工具 → Console
3. 手动修改 localStorage：
   ```javascript
   localStorage.setItem('frame_build_three_scene_state_v1_global_adarc', '0.999');
   ```
4. 等待2-3秒
5. 在 Network 标签中查看是否触发了保存请求

### 4. 跨标签页测试
1. 在两个标签页中打开应用并登录
2. 在标签页A中进行操作
3. 切换到标签页B
4. 检查是否检测到变化并触发保存

### 5. 清除测试
1. 登录并进行操作
2. 点击"获取下一组"按钮
3. 刷新页面
4. 检查是否没有恢复之前的状态（因为已清除）

## 注意事项

1. **性能优化**: 使用了多层防抖和节流，避免频繁保存
2. **数据完整性**: 保存了所有关键的 localStorage 数据
3. **错误处理**: 所有 localStorage 操作都有 try-catch 保护
4. **兼容性**: 支持 JSON 和字符串类型的 localStorage 值
5. **内存管理**: 组件卸载时自动清理监听器

## 完成状态

✅ 保存 mainState 数据
✅ 保存 originalRotationMap 数据
✅ 保存 globalAdArcValue 数据
✅ 保存 originalAdArcMap 数据
✅ 保存 cameraDeltaMap 数据
✅ 恢复所有 localStorage 数据
✅ 自动监听 localStorage 变化
✅ 定期检查机制
✅ 跨标签页监听
✅ 防抖和节流优化
✅ 编译测试通过

## 数据大小估算

假设一个典型的使用场景：
- 6个点位置（positions）：约 0.5 KB
- 12个贝塞尔点（bezierPoints）：约 1 KB
- 3个场景（scenes）：约 1 KB
- mainState：约 2 KB
- originalRotationMap：约 0.5 KB
- globalAdArcValue：约 0.1 KB
- originalAdArcMap：约 0.5 KB
- cameraDeltaMap：约 0.5 KB

**总计**: 约 6-7 KB

这个大小对于数据库存储和网络传输都是非常合理的。
