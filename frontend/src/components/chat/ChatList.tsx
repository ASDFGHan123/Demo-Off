import React, { useState, useEffect } from 'react';
import { Card, ListGroup, Button, Alert, Spinner } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import { chatAPI } from '../../services/api';

interface Conversation {
  conversation_id: number;
  type: 'private' | 'group';
  title?: string;
  last_message?: {
    content: string;
    sent_at: string;
    sender: {
      display_name: string;
    };
  };
}

const ChatList: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      setLoading(true);
      const response = await chatAPI.getConversations();
      setConversations(response.data);
    } catch (err) {
      setError('Failed to load conversations');
      console.error('Error loading conversations:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatLastMessage = (conversation: Conversation) => {
    if (!conversation.last_message) {
      return 'No messages yet';
    }

    const { content, sender, sent_at } = conversation.last_message;
    const date = new Date(sent_at).toLocaleDateString();
    return `${sender.display_name}: ${content.substring(0, 50)}${content.length > 50 ? '...' : ''} (${date})`;
  };

  if (loading) {
    return (
      <div className="text-center">
        <Spinner animation="border" />
        <p>Loading conversations...</p>
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Your Chats</h1>
        <div>
          <Link to="/create-private" className="btn btn-primary me-2">
            New Private Chat
          </Link>
          <Link to="/create-group" className="btn btn-success">
            New Group Chat
          </Link>
        </div>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      {conversations.length === 0 ? (
        <Alert variant="info">
          <h4>No chats yet!</h4>
          <p>Start a conversation to see your chats here.</p>
        </Alert>
      ) : (
        <Card>
          <ListGroup variant="flush">
            {conversations.map((conversation) => (
              <ListGroup.Item
                key={conversation.conversation_id}
                className="d-flex justify-content-between align-items-center"
              >
                <div className="flex-grow-1">
                  <div className="d-flex align-items-center">
                    <strong>
                      {conversation.type === 'private' ? 'Private Chat' : (conversation.title || 'Group Chat')}
                    </strong>
                    <span className="badge bg-primary ms-2">
                      {conversation.type}
                    </span>
                  </div>
                  <small className="text-muted">
                    {formatLastMessage(conversation)}
                  </small>
                </div>
                <Link
                  to={`/chat/${conversation.conversation_id}`}
                  className="btn btn-outline-primary btn-sm"
                >
                  Open Chat
                </Link>
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Card>
      )}
    </div>
  );
};

export default ChatList;