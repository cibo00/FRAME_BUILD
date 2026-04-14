/**
 * OperationManager - 操作管理器
 * 负责管理心跳检测和临时操作保存功能
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
  private sessionToken: string;
  private heartbeatInterval: number | null = null;
  private isActive: boolean = true;
  private heartbeatIntervalMs: number = 30000; // 30秒

  constructor(sessionToken: string) {
    this.sessionToken = sessionToken;
  }

  /**
   * 验证 session token 是否有效
   * @returns 返回 token 是否有效
   */
  async validateToken(): Promise<boolean> {
    try {
      const response = await api.get('/api/validate-session', {
        headers: {
          'Authorization': `Bearer ${this.sessionToken}`
        }
      });

      if (response.status === 200 && response.data.valid) {
        console.log('[OperationManager] Session Token 验证成功');
        return true;
      } else {
        console.log('[OperationManager] Session Token 无效');
        return false;
      }
    } catch (error) {
      console.error('[OperationManager] Session Token 验证失败:', error);
      return false;
    }
  }

  /**
   * 初始化操作管理器
   * @returns 返回保存的临时操作数据，如果没有则返回null
   */
  async init(): Promise<OperationData | null> {
    console.log('[OperationManager] 初始化操作管理器');

    // 启动心跳检测
    this.startHeartbeat();

    // 恢复临时操作
    const savedData = await this.restoreTempOperation();
    return savedData;
  }

  /**
   * 启动心跳检测
   * 每30秒发送一次心跳
   */
  startHeartbeat(): void {
    // 清除之前的定时器（如果存在）
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
    }

    // 立即发送一次心跳
    this.sendHeartbeat();

    // 设置定时器
    this.heartbeatInterval = window.setInterval(() => {
      this.sendHeartbeat();
    }, this.heartbeatIntervalMs);

    console.log('[OperationManager] 心跳检测已启动');
  }

  /**
   * 发送心跳请求
   */
  private async sendHeartbeat(): Promise<void> {
    if (!this.isActive) return;

    try {
      const response = await api.post('/api/heartbeat', {}, {
        headers: {
          'Authorization': `Bearer ${this.sessionToken}`
        }
      });

      if (response.status === 200) {
        console.log('[OperationManager] 心跳发送成功');
      }
    } catch (error) {
      console.error('[OperationManager] 心跳请求错误:', error);
    }
  }

  /**
   * 停止心跳检测
   */
  stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
      console.log('[OperationManager] 心跳检测已停止');
    }
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
          session_token: this.sessionToken,
          operation_data: operationData
        }, {
          headers: {
            'Authorization': `Bearer ${this.sessionToken}`
          }
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
      const response = await api.get('/api/temp-operation/get', {
        headers: {
          'Authorization': `Bearer ${this.sessionToken}`
        }
      });

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
      const response = await api.delete('/api/temp-operation/clear', {
        headers: {
          'Authorization': `Bearer ${this.sessionToken}`
        }
      });

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
    this.stopHeartbeat();
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
