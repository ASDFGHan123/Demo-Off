import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Button, Form, Alert, Spinner, Badge } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { chatAPI } from '../../services/api';
import WebSocketService from '../../services/websocket';

interface Message {
  message_id: number;
  content: string;
  sender: {
    user_id: number;
    username: string;
    display_name: string;
  };
  sent_at: string;
  reply_to?: {
    message_id: number;
    content: string;
    sender: {
      display_name: string;
    };
  };
  attachment?: {
    file_name: string;
    mime_type: string;
    file_size: number;
    file: string;
  };
  reactions: Array<{
    emoji: string;
    count: number;
    users: string[];
  }>;
  is_edited?: boolean;
  is_deleted?: boolean;
}

interface Conversation {
  conversation_id: number;
  type: 'private' | 'group';
  title?: string;
  privatechat?: {
    user1: { user_id: number; display_name: string; is_online: boolean };
    user2: { user_id: number; display_name: string; is_online: boolean };
  };
  groupchat?: {
    groupmember_set: Array<{
      user: { user_id: number; display_name: string; is_online: boolean };
    }>;
  };
}

const ChatDetail: React.FC = () => {
  const { conversationId } = useParams<{ conversationId: string }>();
  const { user } = useAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [socket, setSocket] = useState<any>(null);

  useEffect(() => {
    if (conversationId) {
      loadConversation();
      loadMessages();
      connectWebSocket();
    }

    return () => {
      if (socket) {
        WebSocketService.disconnect();
      }
    };
  }, [conversationId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadConversation = async () => {
    try {
      const response = await chatAPI.getConversation(parseInt(conversationId!));
      setConversation(response.data);
    } catch (err) {
      setError('Failed to load conversation');
      console.error('Error loading conversation:', err);
    }
  };

  const loadMessages = async () => {
    try {
      setLoading(true);
      const response = await chatAPI.getMessages(parseInt(conversationId!));
      setMessages(response.data);
    } catch (err) {
      setError('Failed to load messages');
      console.error('Error loading messages:', err);
    } finally {
      setLoading(false);
    }
  };

  const connectWebSocket = useCallback(async () => {
    if (conversationId) {
      try {
        const ws = await WebSocketService.connect(conversationId);

        WebSocketService.onMessage((data: any) => {
          const newMsg: Message = {
            message_id: data.message_id,
            content: data.message,
            sender: {
              user_id: data.user_id,
              username: data.user,
              display_name: data.user
            },
            sent_at: data.timestamp,
            reply_to: data.reply_to ? {
              message_id: data.reply_to,
              content: data.reply_to_content,
              sender: { display_name: data.reply_to_sender }
            } : undefined,
            attachment: data.attachment,
            reactions: data.reactions || []
          };
          setMessages(prev => [...prev, newMsg]);
        });

        WebSocketService.onReaction((data: any) => {
          setMessages(prev => prev.map(msg =>
            msg.message_id === data.message_id
              ? { ...msg, reactions: data.reactions }
              : msg
          ));
        });

        WebSocketService.onUserStatus((data: any) => {
          // Update user online status in conversation
          setConversation(prev => {
            if (!prev) return prev;
            if (prev.type === 'private') {
              return {
                ...prev,
                privatechat: {
                  ...prev.privatechat!,
                  user1: prev.privatechat!.user1.user_id === data.user_id
                    ? { ...prev.privatechat!.user1, is_online: data.is_online }
                    : prev.privatechat!.user1,
                  user2: prev.privatechat!.user2.user_id === data.user_id
                    ? { ...prev.privatechat!.user2, is_online: data.is_online }
                    : prev.privatechat!.user2
                }
              };
            } else if (prev.type === 'group') {
              return {
                ...prev,
                groupchat: {
                  ...prev.groupchat!,
                  groupmember_set: prev.groupchat!.groupmember_set.map(member => ({
                    ...member,
                    user: member.user.user_id === data.user_id
                      ? { ...member.user, is_online: data.is_online }
                      : member.user
                  }))
                }
              };
            }
            return prev;
          });
        });

        setSocket(ws);
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
        setError('Failed to connect to chat server');
      }
    }
  }, [conversationId]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newMessage.trim() || !conversationId) return;

    try {
      await chatAPI.sendMessage(parseInt(conversationId), newMessage.trim(), replyTo?.message_id);
      setNewMessage('');
      setReplyTo(null);
    } catch (err) {
      console.error('Error sending message:', err);
    }
  };

  const handleReaction = (messageId: number, emoji: string) => {
    WebSocketService.sendReaction(messageId, emoji);
  };

  const handleReply = (message: Message) => {
    setReplyTo(message);
  };

  const cancelReply = () => {
    setReplyTo(null);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const participants = useMemo(() => {
    if (!conversation) return [];
    if (conversation.type === 'private') {
      return [conversation.privatechat!.user1, conversation.privatechat!.user2];
    } else {
      return conversation.groupchat!.groupmember_set.map(m => m.user);
    }
  }, [conversation]);

  if (loading) {
    return (
      <div className="text-center">
        <Spinner animation="border" />
        <p>Loading chat...</p>
      </div>
    );
  }

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <Link to="/chats" className="btn btn-secondary">← Back to Chats</Link>
        <h1>{conversation?.title || 'Chat'}</h1>
        <div></div>
      </div>

      {/* Participants Status */}
      <Card className="mb-3">
        <Card.Body>
          <h6 className="card-title">Participants</h6>
          <div className="d-flex flex-wrap gap-2">
            {participants.map(participant => (
              <div key={participant.user_id} className="d-flex align-items-center">
                <span className="me-2">{participant.display_name}</span>
                <Badge bg={participant.is_online ? 'success' : 'secondary'}>
                  {participant.is_online ? 'Online' : 'Offline'}
                </Badge>
              </div>
            ))}
          </div>
        </Card.Body>
      </Card>

      {/* Messages */}
      <Card className="mb-3">
        <Card.Body>
          <div className="chat-messages p-3" style={{ height: '400px', overflowY: 'auto' }}>
            {messages.map(message => (
              <div
                key={message.message_id}
                className={`message mb-2 ${message.sender.user_id === user?.user_id ? 'message-own' : 'message-other'}`}
              >
                <div className="d-flex justify-content-between align-items-start">
                  <strong>{message.sender.display_name}:</strong>
                  <small className="text-muted ms-2">
                    {new Date(message.sent_at).toLocaleTimeString()}
                  </small>
                </div>
                <div>{message.content}</div>

                {message.reply_to && (
                  <div className="reply-indicator ms-3 mt-1 p-2 border-start">
                    <small className="text-muted">
                      Replying to {message.reply_to.sender.display_name}: {message.reply_to.content.substring(0, 50)}...
                    </small>
                  </div>
                )}

                {message.attachment && (
                  <div className="mt-1">
                    <small>
                      <a href={message.attachment.file} target="_blank" rel="noopener noreferrer">
                        📎 {message.attachment.file_name}
                      </a>
                      ({(message.attachment.file_size / 1024).toFixed(1)} KB)
                    </small>
                  </div>
                )}

                <div className="reactions mt-1">
                  {message.reactions.map((reaction, index: number) => (
                    <Badge key={index} bg="light" text="dark" className="me-1 reaction-button">
                      {reaction.emoji} {reaction.count}
                    </Badge>
                  ))}
                </div>

                <div className="message-actions mt-1">
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    className="me-1"
                    onClick={() => handleReaction(message.message_id, '👍')}
                  >
                    👍
                  </Button>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    className="me-1"
                    onClick={() => handleReaction(message.message_id, '❤️')}
                  >
                    ❤️
                  </Button>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    className="me-1"
                    onClick={() => handleReaction(message.message_id, '😂')}
                  >
                    😂
                  </Button>
                  <Button
                    variant="outline-secondary"
                    size="sm"
                    onClick={() => handleReply(message)}
                  >
                    Reply
                  </Button>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </Card.Body>
      </Card>

      {/* Reply Indicator */}
      {replyTo && (
        <Alert variant="info" className="mb-3">
          <div className="d-flex justify-content-between align-items-center">
            <small>
              Replying to <strong>{replyTo.sender.display_name}</strong>: {replyTo.content.substring(0, 50)}...
            </small>
            <Button variant="close" size="sm" onClick={cancelReply} />
          </div>
        </Alert>
      )}

      {/* Message Input */}
      <Form onSubmit={sendMessage}>
        <div className="input-group">
          <Form.Control
            type="text"
            placeholder="Type a message..."
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            required
          />
          <Button type="submit" variant="primary">
            Send
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default ChatDetail;