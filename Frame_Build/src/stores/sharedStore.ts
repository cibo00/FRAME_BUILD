import { reactive } from 'vue';

// 定义点的数据结构类型
export interface ScenePoint {
    name: string,
    x: number,
    y: number,
    z: number
}

// 定义新增的侧轮廓控制点
export interface SideProfilePoint {
    name: string,
    x: number,
    y: number,
    z: number
}

// 定义共享的状态结构
export const sharedPointsState = reactive<{
    positions: ScenePoint[],
    bezierPoints: ScenePoint[],
    // 全局 AD_arc（以弧度存储），在多个场景间同步
    globalAdArc?: number | null
    // 新增：侧轮廓控制点 G, H, I, J
    sideProfilePoints: SideProfilePoint[],
    // 新增：xy_rotation 参数（弧度）
    xyRotation?: number | null,
    // 新增：A_tangent 参数（弧度）
    aTangent?: number | null
}>( {
    // 初始化数据（您可以从外部加载默认值）
    positions: [
      // { name: 'P1', x: 100, y: 0, z: 0 }, // 示例数据
    ],
    bezierPoints: [],
    // 初始化侧轮廓点（默认值）
    sideProfilePoints: [
        { name: 'G', x: 0, y: 1.0, z: 0.5 },
        { name: 'H', x: 0, y: 1.5, z: 0.3 },
        { name: 'I', x: 7, y: 2.0, z: 0.6 },
        { name: 'J', x: 7, y: 2.5, z: 0.4 }
    ],
    // 初始化参数默认值
    xyRotation: 0.0,
    aTangent: Math.PI / 10  // 默认 18度
});
