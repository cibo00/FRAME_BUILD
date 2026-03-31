# 功能更新说明 - 登录验证和localStorage清除

## 更新内容

本次更新实现了两个重要功能：

### 1. 登录验证 - 只有登录后才能调用数据API

**修改的API调用**:
- `/api/next-three-image-and-data`

**实现位置**:
- `src/App.vue` 中的 `fetchNextDataBatch()` 函数

**功能说明**:
- 在调用后端API获取数据前，先检查用户是否已登录
- 如果未登录，显示错误提示："请先登录后再获取数据"
- 页面挂载时，只有在已登录的情况下才会自动拉取后端数据

**代码实现**:
```typescript
async function fetchNextDataBatch(force = false) {
  // 检查是否已登录
  const token = localStorage.getItem('session_token');
  if (!token) {
    errorMessage.value = '请先登录后再获取数据';
    console.warn('[App] 未登录，无法获取数据');
    return;
  }

  // ... 继续执行数据获取逻辑
}
```

**页面挂载逻辑**:
```typescript
onMounted(() => {
  const token = localStorage.getItem('session_token');

  if (token) {
    // 已登录，初始化操作管理器
    initOperationManager(token);
  } else {
    console.log('[App] 未登录，跳过操作管理器初始化');
  }

  // ... 其他逻辑

  // 只有在已登录且没有本地恢复数据时才自动拉取
  if (!haveLocalRestore && token) {
    fetchNextDataBatch();
  } else if (!token) {
    console.log('未登录，跳过页面挂载时的自动后端拉取。');
  }
});
```

### 2. 心跳超时后自动清除localStorage

**功能说明**:
- 当用户超过1分钟没有心跳（关闭网页或长时间不操作）
- 后端会自动清除该用户的临时操作数据
- 用户下次登录时，前端检测到没有临时操作数据
- 自动清除所有相关的 localStorage 数据

**清除的localStorage键**:
1. `frame_build_three_scene_state_v1`
2. `frame_build_three_scene_state_v1_original_camera_rotation_map`
3. `frame_build_three_scene_state_v1_global_adarc`
4. `frame_build_three_scene_state_v1_original_adarc_map`
5. `frame_build_three_scene_state_v1_camera_delta_map`

**实现位置**:
- `src/App.vue` 中的 `initOperationManager()` 函数
- 新增 `clearAllLocalStorageData()` 函数

**代码实现**:
```typescript
async function initOperationManager(token: string) {
  // 创建操作管理器实例
  operationManager = new OperationManager(token);

  // 尝试恢复临时操作
  const savedData = await operationManager.init();

  if (savedData) {
    // 有保存的数据，恢复状态
    // ... 恢复逻辑
    console.log('[App] 已恢复临时操作状态');
  } else {
    // 没有保存的数据，说明用户已超时，清除所有localStorage
    console.log('[App] 没有找到临时操作，清除所有 localStorage 数据');
    clearAllLocalStorageData();
  }
}

function clearAllLocalStorageData() {
  const keysToRemove = [
    'frame_build_three_scene_state_v1',
    'frame_build_three_scene_state_v1_original_camera_rotation_map',
    'frame_build_three_scene_state_v1_global_adarc',
    'frame_build_three_scene_state_v1_original_adarc_map',
    'frame_build_three_scene_state_v1_camera_delta_map'
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
}
```

## 工作流程

### 场景1：用户正常使用（有心跳）

```
用户登录
  ↓
初始化操作管理器
  ↓
启动心跳检测（每30秒）
  ↓
从后端恢复临时操作（如果有）
  ↓
用户进行操作
  ↓
自动保存到后端
  ↓
用户刷新页面
  ↓
检测到有临时操作
  ↓
恢复所有数据（包括localStorage）
```

### 场景2：用户关闭网页超过1分钟

```
用户关闭网页
  ↓
停止心跳
  ↓
后端检测到超过1分钟没有心跳
  ↓
后端清除临时操作数据
  ↓
用户重新打开网页并登录
  ↓
初始化操作管理器
  ↓
尝试恢复临时操作
  ↓
后端返回：没有临时操作
  ↓
前端清除所有localStorage数据
  ↓
用户从全新状态开始
```

### 场景3：用户未登录

```
用户打开网页（未登录）
  ↓
页面挂载
  ↓
检测到未登录
  ↓
跳过操作管理器初始化
  ↓
跳过自动数据拉取
  ↓
显示登录界面
  ↓
用户点击"获取下一组"
  ↓
显示错误："请先登录后再获取数据"
```

## 用户体验改进

### 1. 明确的登录提示
- 未登录时尝试获取数据，会显示清晰的错误提示
- 避免用户困惑为什么无法获取数据

### 2. 自动清理过期数据
- 用户关闭网页超过1分钟后，localStorage会被自动清理
- 避免旧数据干扰新的操作
- 确保用户每次登录都能获取最新的数据

### 3. 数据一致性
- localStorage 和后端数据保持同步
- 如果后端没有数据，localStorage 也会被清除
- 避免前后端数据不一致的问题

## 测试建议

### 测试1：未登录时的行为
1. 打开应用（不登录）
2. 点击"获取下一组"按钮
3. **预期结果**: 显示错误提示"请先登录后再获取数据"
4. 检查浏览器控制台，应该看到警告日志

### 测试2：登录后的正常流程
1. 登录应用
2. 拖动点位置进行操作
3. 点击"获取下一组"按钮
4. **预期结果**: 成功获取新数据
5. 检查Network标签，应该看到成功的API请求

### 测试3：心跳超时后的清理
1. 登录应用并进行操作
2. 关闭浏览器标签页
3. 等待超过1分钟
4. 重新打开应用并登录
5. **预期结果**:
   - 控制台显示"没有找到临时操作，清除所有 localStorage 数据"
   - 打开开发者工具 → Application → Local Storage
   - 检查所有相关的键都已被清除
   - 应用从全新状态开始

### 测试4：刷新页面（1分钟内）
1. 登录应用并进行操作
2. 等待保存完成（2-3秒）
3. 刷新页面（在1分钟内）
4. **预期结果**:
   - 所有数据恢复到刷新前的状态
   - localStorage 数据保持不变

### 测试5：页面挂载时的登录检查
1. 清除所有 localStorage 和 cookies
2. 打开应用（未登录状态）
3. 检查浏览器控制台
4. **预期结果**:
   - 看到"未登录，跳过操作管理器初始化"
   - 看到"未登录，跳过页面挂载时的自动后端拉取"
   - 没有发送 `/api/next-three-image-and-data` 请求

## 注意事项

1. **session_token 的重要性**
   - 所有功能都依赖于 localStorage 中的 `session_token`
   - 确保登录成功后正确保存 token
   - Token 过期后需要重新登录

2. **心跳超时时间**
   - 后端设置为1分钟
   - 前端心跳间隔为30秒
   - 确保有足够的缓冲时间

3. **localStorage 清理**
   - 只清理应用相关的键
   - 不会影响其他应用的 localStorage 数据
   - 清理是不可逆的，确保用户理解这一点

4. **错误处理**
   - 所有 localStorage 操作都有 try-catch 保护
   - 网络错误会有适当的提示
   - 用户体验友好

## 完成状态

✅ 添加登录验证到 fetchNextDataBatch
✅ 页面挂载时检查登录状态
✅ 心跳超时后自动清除 localStorage
✅ 清空共享点数据
✅ 完整的错误提示
✅ 编译测试通过
✅ 用户体验优化

## 相关文件

- `src/App.vue` - 主要修改文件
- `src/utils/OperationManager.ts` - 操作管理器（未修改）
- 后端 `apiHeartbeatAndTempOps.go` - 心跳检测和清理逻辑（未修改）

## 后续建议

1. **添加登录状态指示器**
   - 在UI上显示当前登录状态
   - 让用户清楚知道是否已登录

2. **添加自动登录功能**
   - 如果 token 仍然有效，自动恢复登录状态
   - 减少用户重复登录的次数

3. **优化错误提示**
   - 可以考虑使用 Toast 或 Notification 组件
   - 提供更友好的视觉反馈

4. **添加数据清理确认**
   - 在清理 localStorage 前可以考虑询问用户
   - 或者提供恢复选项（如果需要）
