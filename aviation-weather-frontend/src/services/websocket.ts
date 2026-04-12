/**
 * WebSocket服务 - 实时METAR数据推送
 */

export interface METARUpdate {
  icao: string;
  metar_raw: string;
  metar_parsed: any;
  timestamp: string;
}

export type METARUpdateCallback = (update: METARUpdate) => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private subscribers: Map<string, Set<METARUpdateCallback>> = new Map();
  private isConnected = false;
  private url: string = '';

  /**
   * 连接WebSocket服务器
   * @param url WebSocket服务器地址
   */
  connect(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws && this.isConnected) {
        resolve();
        return;
      }

      this.url = url;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('WebSocket连接成功');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket连接关闭');
        this.isConnected = false;
        this.attemptReconnect();
      };
    });
  }

  /**
   * 处理接收到的消息
   */
  private handleMessage(data: any): void {
    if (data.type === 'metar_update' && data.icao) {
      const update: METARUpdate = {
        icao: data.icao,
        metar_raw: data.metar_raw,
        metar_parsed: data.metar_parsed,
        timestamp: data.timestamp || new Date().toISOString()
      };

      // 通知所有订阅了该机场的回调
      const callbacks = this.subscribers.get(data.icao);
      if (callbacks) {
        callbacks.forEach(callback => {
          try {
            callback(update);
          } catch (error) {
            console.error('回调执行错误:', error);
          }
        });
      }

      // 通知订阅了"all"的回调
      const allCallbacks = this.subscribers.get('all');
      if (allCallbacks) {
        allCallbacks.forEach(callback => {
          try {
            callback(update);
          } catch (error) {
            console.error('回调执行错误:', error);
          }
        });
      }
    }
  }

  /**
   * 尝试重新连接
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('达到最大重连次数，停止重连');
      return;
    }

    this.reconnectAttempts++;
    console.log(`尝试重新连接 (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      if (this.url) {
        this.connect(this.url).catch(error => {
          console.error('重连失败:', error);
        });
      }
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  /**
   * 订阅机场METAR更新
   * @param icao 机场ICAO代码，'all'表示订阅所有机场
   * @param callback 回调函数
   */
  subscribe(icao: string, callback: METARUpdateCallback): () => void {
    const icaoUpper = icao.toUpperCase();
    
    if (!this.subscribers.has(icaoUpper)) {
      this.subscribers.set(icaoUpper, new Set());
    }
    
    this.subscribers.get(icaoUpper)!.add(callback);

    // 如果已连接，发送订阅请求
    if (this.isConnected && this.ws) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        icao: icaoUpper
      }));
    }

    // 返回取消订阅函数
    return () => {
      this.unsubscribe(icaoUpper, callback);
    };
  }

  /**
   * 取消订阅
   * @param icao 机场ICAO代码
   * @param callback 回调函数
   */
  unsubscribe(icao: string, callback: METARUpdateCallback): void {
    const icaoUpper = icao.toUpperCase();
    const callbacks = this.subscribers.get(icaoUpper);
    
    if (callbacks) {
      callbacks.delete(callback);
      
      // 如果没有订阅者了，发送取消订阅请求
      if (callbacks.size === 0) {
        this.subscribers.delete(icaoUpper);
        
        if (this.isConnected && this.ws) {
          this.ws.send(JSON.stringify({
            type: 'unsubscribe',
            icao: icaoUpper
          }));
        }
      }
    }
  }

  /**
   * 断开连接
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
      this.subscribers.clear();
    }
  }

  /**
   * 检查连接状态
   */
  getConnectionStatus(): boolean {
    return this.isConnected;
  }

  /**
   * 获取订阅的机场列表
   */
  getSubscribedAirports(): string[] {
    return Array.from(this.subscribers.keys());
  }
}

// 创建全局实例
let websocketServiceInstance: WebSocketService | null = null;

export function getWebSocketService(): WebSocketService {
  if (!websocketServiceInstance) {
    websocketServiceInstance = new WebSocketService();
  }
  return websocketServiceInstance;
}