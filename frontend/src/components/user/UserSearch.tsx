import React, { useState } from 'react';
import { Form, Button, Card, ListGroup, Alert, Spinner, Badge } from 'react-bootstrap';
import { userAPI, chatAPI } from '../../services/api';
import { useNavigate } from 'react-router-dom';

interface User {
  user_id: number;
  username: string;
  display_name: string;
  profile_image_url?: string;
  is_online: boolean;
}

const UserSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError('');

    try {
      const response = await userAPI.searchUsers(query.trim());
      setResults(response.data.results || []);
    } catch (err) {
      setError('Failed to search users');
      console.error('Error searching users:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePrivateChat = async (userId: number) => {
    try {
      const response = await chatAPI.createPrivateChat(userId);
      navigate(`/chat/${response.data.conversation_id}`);
    } catch (err) {
      setError('Failed to create chat');
      console.error('Error creating private chat:', err);
    }
  };

  return (
    <div>
      <h1 className="mb-4">Search Users</h1>

      <Card className="mb-4">
        <Card.Body>
          <Form onSubmit={handleSearch}>
            <Form.Group className="mb-3">
              <Form.Label>Search for users</Form.Label>
              <div className="input-group">
                <Form.Control
                  type="text"
                  placeholder="Enter username or display name..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  required
                />
                <Button type="submit" variant="primary" disabled={loading}>
                  {loading ? <Spinner animation="border" size="sm" /> : 'Search'}
                </Button>
              </div>
            </Form.Group>
          </Form>
        </Card.Body>
      </Card>

      {error && <Alert variant="danger">{error}</Alert>}

      {results.length > 0 && (
        <Card>
          <Card.Header>
            <h5 className="mb-0">Search Results</h5>
          </Card.Header>
          <ListGroup variant="flush">
            {results.map(user => (
              <ListGroup.Item key={user.user_id} className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center">
                  {user.profile_image_url && (
                    <img
                      src={user.profile_image_url}
                      alt={user.display_name}
                      className="rounded-circle me-3"
                      style={{ width: '40px', height: '40px', objectFit: 'cover' }}
                    />
                  )}
                  <div>
                    <div className="fw-bold">{user.display_name}</div>
                    <small className="text-muted">@{user.username}</small>
                  </div>
                  <Badge bg={user.is_online ? 'success' : 'secondary'} className="ms-2">
                    {user.is_online ? 'Online' : 'Offline'}
                  </Badge>
                </div>
                <Button
                  variant="outline-primary"
                  size="sm"
                  onClick={() => handleCreatePrivateChat(user.user_id)}
                >
                  Start Chat
                </Button>
              </ListGroup.Item>
            ))}
          </ListGroup>
        </Card>
      )}

      {query && !loading && results.length === 0 && (
        <Alert variant="info">
          No users found matching "{query}"
        </Alert>
      )}
    </div>
  );
};

export default UserSearch;