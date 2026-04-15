/**
 * OperationManager - 操作管理器
 * 负责管理临时操作保存功能
 */

import { api } from '@/api';

export interface OperationData {
  positions?: any[];
  bezierPoints?: any[];
  scenes?: any[];
  globalADArc?: number;
  [key: string]: any;
}

export class OperationManager {
  private isActive: boolean = true;

  constructor(sessionToken: string) {
    // sessionToken 参数保留兼容，不再使用
  }

  /**
   * 验证 session token 是否有效
   * @returns 始终返回 true（无需验证）
   */
  async validateToken(): Promise<boolean> {
    return true;
  }

  /**
   * 初始化操作管理器
   * @returns 返回保存的临时操作数据，如果没有则返回null
   */
  async init(): Promise<OperationData | null> {
    console.log('[OperationManager] 初始化操作管理器');

    // 恢复临时操作
    const savedData = await this.restoreTempOperation();
    return savedData;
  }

  /**
   * 保存临时操作（带防抖）
   * @param operationData 要保存的操作数据
   */
  private saveTempOperationDebounced = this.debounce(
    async (operationData: OperationData) => {
      if (!this.isActive) return;

      try {
        const response = await api.post('/api/temp-operation/save', {
          operation_data: operationData
        });

        if (response.status === 200) {
          console.log('[OperationManager] 临时操作已保存');
        }
      } catch (error) {
        console.error('[OperationManager] 保存请求错误:', error);
      }
    },
    500
  );

  /**
   * 保存临时操作（公开方法）
   * @param operationData 要保存的操作数据
   */
  saveTempOperation(operationData: OperationData): void {
    this.saveTempOperationDebounced(operationData);
  }

  /**
   * 恢复临时操作
   * @returns 返回保存的操作数据，如果没有则返回null
   */
  async restoreTempOperation(): Promise<OperationData | null> {
    try {
      const response = await api.get('/api/temp-operation/get');

      if (response.status === 200 && response.data.operation_data) {
        console.log('[OperationManager] 已恢复临时操作');
        return response.data.operation_data;
      } else {
        console.log('[OperationManager] 没有找到临时操作');
        return null;
      }
    } catch (error) {
      console.error('[OperationManager] 获取临时操作错误:', error);
      return null;
    }
  }

  /**
   * 清除临时操作
   * @returns 返回是否清除成功
   */
  async clearTempOperation(): Promise<boolean> {
    try {
      const response = await api.delete('/api/temp-operation/clear');

      if (response.status === 200) {
        console.log('[OperationManager] 临时操作已清除');
        return true;
      }
      return false;
    } catch (error) {
      console.error('[OperationManager] 清除临时操作错误:', error);
      return false;
    }
  }

  /**
   * 销毁操作管理器
   */
  destroy(): void {
    this.isActive = false;
    console.log('[OperationManager] 操作管理器已销毁');
  }

  /**
   * 防抖函数
   * @param func 要防抖的函数
   * @param wait 等待时间（毫秒）
   * @returns 防抖后的函数
   */
  private debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number
  ): (...args: Parameters<T>) => void {
    let timeout: number | null = null;
    return function (this: any, ...args: Parameters<T>) {
      if (timeout !== null) {
        clearTimeout(timeout);
      }
      timeout = window.setTimeout(() => {
        func.apply(this, args);
      }, wait);
    };
  }
}
