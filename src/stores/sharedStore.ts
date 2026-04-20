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
    // 侧轮廓点：G, H, A_P1_G, A_P1_H, J, I, D_P1_J, D_P1_I
    sideProfilePoints: SideProfilePoint[],
    // xy_rotation 参数（弧度）
    xyRotation?: number | null,
    // A_tangent 参数（弧度）
    aTangent?: number | null,
    // 全局设置（来自后端或用户输入）
    fingerType?: string | null,
    focalLengthMm?: number | null,
    sensorWidthMm?: number | null,
}>( {
    // 初始化数据（您可以从外部加载默认值）
    positions: [
      // { name: 'P1', x: 100, y: 0, z: 0 }, // 示例数据
    ],
    bezierPoints: [],
    // 侧轮廓点（默认值，实际值由 ThreeScene 同步）
    sideProfilePoints: [
        // 根部侧轮廓
        { name: 'G', x: -3.0, y: -0.8, z: 0 },
        { name: 'H', x: 3.2, y: -0.8, z: 0 },
        { name: 'A_P1_G', x: -2.0, y: 0.0, z: 0 },
        { name: 'A_P1_H', x: 2.0, y: 0.0, z: 0 },
        // 尖端侧轮廓
        { name: 'J', x: -4.0, y: -1.2, z: 0 },
        { name: 'I', x: 4.2, y: -1.2, z: 0 },
        { name: 'D_P1_J', x: -3.0, y: 0.0, z: 0 },
        { name: 'D_P1_I', x: 3.0, y: 0.0, z: 0 },
    ],
    // 参数默认值
    xyRotation: 0.0,
    aTangent: 86 * Math.PI / 180  // 默认 86度 (∠+Z, AD')
});
