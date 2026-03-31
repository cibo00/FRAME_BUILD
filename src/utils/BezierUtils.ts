import * as THREE from 'three';

// --- 1. 自定义贝塞尔曲线的数学辅助函数 ---
// 这些函数是内部使用的，所以我们不导出 (export) 它们

/**
 * 计算阶乘 (n!)
 * @param n 非负整数
 */
function factorial(n: number): number {
  if (n < 0) return 0;
  if (n === 0) return 1;
  let result = 1;
  for (let i = 2; i <= n; i++) {
    result *= i;
  }
  return result;
}

/**
 * 计算二项式系数 C(n, k) 或 "n choose k"
 * @param n 总数
 * @param k 选择数
 */
function binomialCoefficient(n: number, k: number): number {
  if (k < 0 || k > n) {
    return 0;
  }
  return factorial(n) / (factorial(k) * factorial(n - k));
}


// --- 2. 移植自 Python 的自定义 N 阶贝塞尔曲线类 ---
// 我们导出 (export) 这个类，以便其他文件（如 ThreeScene.vue）可以使用它
export class BezierCurve {
  controlPoints: THREE.Vector3[];
  degree: number;
  /**
   * 根据一组控制点初始化一个N阶贝塞尔曲线
   * @param controlPoints 控制点数组 (THREE.Vector3[])
   */
  constructor(controlPoints: THREE.Vector3[]) {
    this.controlPoints = controlPoints;
    this.degree = this.controlPoints.length - 1;
  }

  /**
   * 根据参数 t (0 到 1) 计算曲线上的点
   * 这段逻辑与您 Python 代码中的 'evaluate' 方法完全相同
   * @param t 参数，范围 [0, 1]
   * @returns 曲线上的点 (THREE.Vector3)
   */
  getPoint(t: number): THREE.Vector3 {
    const point = new THREE.Vector3(0, 0, 0);
    for (let j = 0; j <= this.degree; j++) {
      const coef = binomialCoefficient(this.degree, j) * Math.pow(t, j) * Math.pow(1 - t, this.degree - j);
      point.addScaledVector(this.controlPoints[j], coef);
    }
    return point;
  }

  /**
   * 生成一系列点来近似整条曲线
   * @param divisions 曲线的分段数
   * @returns 构成曲线的点数组 (THREE.Vector3[])
   */
  getPoints(divisions: number = 50): THREE.Vector3[] {
    const points: THREE.Vector3[] = [];
    for (let i = 0; i <= divisions; i++) {
      points.push(this.getPoint(i / divisions));
    }
    return points;
  }

  
   
  // 修复：添加 evaluate 方法
    public evaluate(t: number): THREE.Vector3 {
        if (t < 0 || t > 1) {
            console.error("Parameter 't' must be between 0 and 1.");
            return new THREE.Vector3();
        }

        const evaluate_degree = this.controlPoints.length - 1;
        const point = new THREE.Vector3();

        for (let j = 0; j <= evaluate_degree; j++) {
            // 使用 Three.js 的插值方法或者手动实现
            const coef = this.binomialCoefficient(evaluate_degree, j) * Math.pow(1 - t, evaluate_degree - j) * Math.pow(t, j);
            point.addScaledVector(this.controlPoints[j], coef);
        }

        return point;
    }

    private binomialCoefficient(n: number, k: number): number {
        if (k < 0 || k > n) {
            return 0;
        }
        if (k === 0 || k === n) {
            return 1;
        }
        if (k > n / 2) {
            k = n - k;
        }
        let res = 1;
        for (let i = 1; i <= k; ++i) {
            res = res * (n - i + 1) / i;
        }
        return res;
    }

}
