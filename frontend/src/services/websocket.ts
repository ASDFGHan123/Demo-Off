class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private lastHeartbeat = Date.now();
  private messageCallbacks: ((data: any) => void)[] = [];
  private reactionCallbacks: ((data: any) => void)[] = [];
  private userStatusCallbacks: ((data: any) => void)[] = [];
  private notificationCallbacks: ((data: any) => void)[] = [];
  private messageEditedCallbacks: ((data: any) => void)[] = [];
  private messageDeletedCallbacks: ((data: any) => void)[] = [];
  private readReceiptCallbacks: ((data: any) => void)[] = [];
  private connectionPromise: Promise<WebSocket> | null = null;

  connect(roomName: string): Promise<WebSocket> {
    console.log(`[WebSocket Debug] Attempting to connect to room: ${roomName}`);
    if (this.connectionPromise) {
      console.log('[WebSocket Debug] Returning existing connection promise');
      return this.connectionPromise;
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        console.log('[WebSocket Debug] Socket already open, resolving immediately');
        resolve(this.socket);
        return;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/chat/${roomName}/`;
      console.log(`[WebSocket Debug] Connecting to URL: ${wsUrl}`);

      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('[WebSocket Debug] WebSocket connected successfully');
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        resolve(this.socket!);
      };

      this.socket.onclose = (event) => {
        console.log(`[WebSocket Debug] WebSocket disconnected: code=${event.code}, reason=${event.reason}, wasClean=${event.wasClean}`);
        this.stopHeartbeat();
        this.connectionPromise = null;
        if (event.code !== 1000) { // Not a normal closure
          console.log('[WebSocket Debug] Non-normal closure, attempting reconnect');
          this.attemptReconnect(roomName);
        } else {
          console.log('[WebSocket Debug] Normal closure, not reconnecting');
        }
      };

      this.socket.onerror = (error) => {
        console.error('[WebSocket Debug] WebSocket connection error:', error);
        this.connectionPromise = null;
        reject(error);
        this.attemptReconnect(roomName);
      };

      this.socket.onmessage = (event) => {
        console.log(`[WebSocket Debug] Received message: ${event.data.substring(0, 100)}${event.data.length > 100 ? '...' : ''}`);
        this.lastHeartbeat = Date.now();
        try {
          const data = JSON.parse(event.data);
          console.log(`[WebSocket Debug] Parsed message type: ${data.type || 'regular_message'}`);
          this.handleMessage(data);
        } catch (e) {
          console.error('[WebSocket Debug] Failed to parse WebSocket message:', e, 'Raw data:', event.data);
        }
      };
    });

    return this.connectionPromise;
  }

  private handleMessage(data: any) {
    console.log(`[WebSocket Debug] Handling message type: ${data.type || 'regular_message'}`);
    if (data.type === 'reaction') {
      console.log('[WebSocket Debug] Processing reaction message');
      this.reactionCallbacks.forEach(callback => callback(data));
    } else if (data.type === 'user_status') {
      console.log('[WebSocket Debug] Processing user status message');
      this.userStatusCallbacks.forEach(callback => callback(data));
    } else if (data.type === 'notification') {
      console.log('[WebSocket Debug] Processing notification message');
      this.notificationCallbacks.forEach(callback => callback(data));
    } else if (data.type === 'message_edited') {
      console.log('[WebSocket Debug] Processing message edited message');
      this.messageEditedCallbacks.forEach(callback => callback(data));
    } else if (data.type === 'message_deleted') {
      console.log('[WebSocket Debug] Processing message deleted message');
      this.messageDeletedCallbacks.forEach(callback => callback(data));
    } else if (data.type === 'read_receipt') {
      console.log('[WebSocket Debug] Processing read receipt message');
      this.readReceiptCallbacks.forEach(callback => callback(data));
    } else {
      // Assume it's a regular message
      console.log('[WebSocket Debug] Processing regular message');
      this.messageCallbacks.forEach(callback => callback(data));
    }
  }

  private startHeartbeat() {
    this.heartbeatInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        // Send ping every 30 seconds
        this.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    // Check for pong responses
    this.socket!.onmessage = (event) => {
      this.lastHeartbeat = Date.now();
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') {
          return; // Heartbeat response, don't process as message
        }
        this.handleMessage(data);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private attemptReconnect(roomName: string) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

      this.reconnectTimeout = setTimeout(() => {
        this.connect(roomName).catch(() => {
          // Connection failed, will retry in next attempt
        });
      }, this.reconnectDelay * this.reconnectAttempts);
    } else {
      console.error('Max reconnection attempts reached');
    }
  }

  disconnect() {
    this.stopHeartbeat();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }
    this.connectionPromise = null;
    this.reconnectAttempts = 0;
  }

  sendMessage(message: any) {
    console.log(`[WebSocket Debug] Sending message: ${JSON.stringify(message)}`);
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const payload = JSON.stringify({
        message: message.message,
        reply_to: message.reply_to
      });
      console.log(`[WebSocket Debug] Sending payload: ${payload}`);
      this.socket.send(payload);
    } else {
      console.error('[WebSocket Debug] Cannot send message: socket not open or null');
    }
  }

  sendReaction(messageId: number, emoji: string) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'reaction',
        message_id: messageId,
        emoji
      }));
    }
  }

  sendReadReceipt(messageId: number) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'read_receipt',
        message_id: messageId
      }));
    }
  }

  editMessage(messageId: number, content: string) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'edit_message',
        message_id: messageId,
        content
      }));
    }
  }

  deleteMessage(messageId: number) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: 'delete_message',
        message_id: messageId
      }));
    }
  }

  replyToMessage(messageId: number, content: string, replyToId?: number) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        message: content,
        reply_to: replyToId
      }));
    }
  }

  onMessage(callback: (data: any) => void) {
    this.messageCallbacks.push(callback);
  }

  onReaction(callback: (data: any) => void) {
    this.reactionCallbacks.push(callback);
  }

  onUserStatus(callback: (data: any) => void) {
    this.userStatusCallbacks.push(callback);
  }

  onNotification(callback: (data: any) => void) {
    this.notificationCallbacks.push(callback);
  }

  onMessageEdited(callback: (data: any) => void) {
    this.messageEditedCallbacks.push(callback);
  }

  onMessageDeleted(callback: (data: any) => void) {
    this.messageDeletedCallbacks.push(callback);
  }

  onReadReceipt(callback: (data: any) => void) {
    this.readReceiptCallbacks.push(callback);
  }

  off(event: string, callback?: (data: any) => void) {
    let callbacks: ((data: any) => void)[] = [];
    switch (event) {
      case 'message':
        callbacks = this.messageCallbacks;
        break;
      case 'reaction':
        callbacks = this.reactionCallbacks;
        break;
      case 'user_status':
        callbacks = this.userStatusCallbacks;
        break;
      case 'notification':
        callbacks = this.notificationCallbacks;
        break;
      case 'message_edited':
        callbacks = this.messageEditedCallbacks;
        break;
      case 'message_deleted':
        callbacks = this.messageDeletedCallbacks;
        break;
      case 'read_receipt':
        callbacks = this.readReceiptCallbacks;
        break;
    }
    if (callback) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    } else {
      callbacks.length = 0;
    }
  }
}

export default new WebSocketService();