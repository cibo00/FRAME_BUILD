<script setup lang="ts">
import { ref, computed } from 'vue'
import ThreeScene from './ThreeScene.vue'
import { sharedPointsState } from '@/stores/sharedStore.ts'
import { onMounted, watch } from 'vue'

// 接收父组件传递过来的多个场景的数据
const props = defineProps<{
  scenesData: any[],
  onSave: () => void,           // 保存函数
  isSaving: boolean             // 保存状态
}>()

const ACTIVE_INDEX_KEY = 'frame_build_active_scene_index_v1'

// 在 setup 同步初始化 activeSceneIndex，确保子组件在第一次渲染时得到正确索引（避免竞态）
let initialIdx = 0;
try {
  const raw = localStorage.getItem(ACTIVE_INDEX_KEY);
  if (raw !== null) {
    const parsed = Number(raw);
    if (!Number.isNaN(parsed) && parsed >= 0) initialIdx = parsed;
  }
} catch (e) { /* ignore */ }
const activeSceneIndex = ref<number>(initialIdx)

function loadSceneToShared(index: number) {
  if (!props.scenesData || !Array.isArray(props.scenesData) || props.scenesData.length === 0) return;
  // Persist active index only. Points are shared globally via sharedPointsState,
  // do NOT copy per-scene positions into the shared store — all scenes use the same points.
  try { localStorage.setItem(ACTIVE_INDEX_KEY, String(index)); } catch(e) {}
}

const activeSceneData = computed(() => props.scenesData[activeSceneIndex.value]);

function prevScene() {
  if (activeSceneIndex.value > 0) {
    activeSceneIndex.value--
    loadSceneToShared(activeSceneIndex.value)
  }
}

function nextScene() {
  if (activeSceneIndex.value < props.scenesData.length - 1) {
    activeSceneIndex.value++
    loadSceneToShared(activeSceneIndex.value)
  }
}

onMounted(() => {
  // try restore last active index
  try {
    const raw = localStorage.getItem(ACTIVE_INDEX_KEY);
    if (raw) {
      const idx = Number(raw);
      if (!Number.isNaN(idx) && idx >= 0 && idx < props.scenesData.length) {
        activeSceneIndex.value = idx;
      }
    }
  } catch(e) {}
  // load initial scene positions into shared store
  loadSceneToShared(activeSceneIndex.value)
})

// Watch for external changes to scenesData (e.g., fetched from backend) and ensure index is valid
watch(() => props.scenesData, (newVal) => {
  if (!Array.isArray(newVal) || newVal.length === 0) return;
  // try to restore persisted active index when scenes become available
  try {
    const raw = localStorage.getItem(ACTIVE_INDEX_KEY);
    if (raw !== null) {
      const idx = Number(raw);
      if (!Number.isNaN(idx) && idx >= 0 && idx < newVal.length) {
        activeSceneIndex.value = idx;
        loadSceneToShared(activeSceneIndex.value);
        return;
      }
    }
  } catch (e) { /* ignore */ }

  // otherwise ensure index is within bounds
  if (activeSceneIndex.value >= newVal.length) {
    activeSceneIndex.value = 0;
  }
  loadSceneToShared(activeSceneIndex.value)
})
</script>

<template>
  <div class="side-panel">
    <div class="controls-column">
      <h2>工作区</h2>
      <button 
        @click="props.onSave" 
        :disabled="props.isSaving || props.scenesData.length === 0"
        class="save-button"
      >
        {{ props.isSaving ? '正在打包...' : '保存点数据' }}
      </button>

      <div class="pagination">
        <button @click="prevScene" :disabled="activeSceneIndex === 0">上一页</button>
        <span class="scene-info">场景 {{ activeSceneIndex + 1 }} / {{ props.scenesData.length }}</span>
        <button @click="nextScene" :disabled="activeSceneIndex === props.scenesData.length - 1">下一页</button>
      </div>
    </div>

    <div class="scene-wrapper">
      <ThreeScene 
        v-if="activeSceneData"
        :sceneData="activeSceneData"
        :activeIndex="activeSceneIndex"
      />
    </div>
  </div>
</template>

<style scoped>
.side-panel {
  display: flex;         /* 开启横向排列 */
  flex-direction: row;   /* 确保子元素左右分布 */
  padding: 15px;
  gap: 20px;             /* 控制左侧控件和右侧 3D 的间距 */
  align-items: flex-start;
  width: 100%;
}

.controls-column {
  flex: 0 0 200px;       /* 固定左侧宽度，不被挤压 */
  display: flex;
  flex-direction: column; /* 内部按钮和分页依然上下排 */
}

.scene-wrapper {
  flex: 1;               /* 占据右侧所有剩余空间 */
}

/* 强制修改 ThreeScene 内部 canvas 的尺寸 */
.scene-wrapper :deep(.three-canvas) {
  width: 600px !important;  /* 你的目标宽度 */
  height: 600px !important; /* 你的目标高度 */
  border: 1px solid #ddd;
  background-color: #000;
}

.save-button {
    margin-bottom: 15px;
    padding: 10px 20px;
    background-color: #007bff; /* 蓝色保存按钮 */
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    transition: background-color 0.3s;
}
.save-button:hover:not(:disabled) {
    background-color: #0056b3;
}
.save-button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
}
.pagination {
  display: flex;
  flex-direction: column; 
  gap: 8px;
  align-items: center;
}


</style>