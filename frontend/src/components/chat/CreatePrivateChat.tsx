import React, { useState, useEffect } from 'react';
import { Form, Button, Card, Alert, Spinner } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { userAPI, chatAPI } from '../../services/api';

interface User {
  user_id: number;
  username: string;
  display_name: string;
  is_online: boolean;
}

const CreatePrivateChat: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await userAPI.getUsers();
      setUsers(response.data);
    } catch (err) {
      setError('Failed to load users');
      console.error('Error loading users:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUserId) return;

    setCreating(true);
    setError('');

    try {
      const response = await chatAPI.createPrivateChat(selectedUserId);
      navigate(`/chat/${response.data.conversation_id}`);
    } catch (err) {
      setError('Failed to create chat');
      console.error('Error creating private chat:', err);
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="text-center">
        <Spinner animation="border" />
        <p>Loading users...</p>
      </div>
    );
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-4">
        <Card>
          <Card.Header>
            <h3 className="text-center mb-0">Create Private Chat</h3>
          </Card.Header>
          <Card.Body>
            {error && <Alert variant="danger">{error}</Alert>}

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>Select User</Form.Label>
                <Form.Select
                  value={selectedUserId || ''}
                  onChange={(e) => setSelectedUserId(parseInt(e.target.value))}
                  required
                >
                  <option value="">Choose a user...</option>
                  {users.map(user => (
                    <option key={user.user_id} value={user.user_id}>
                      {user.display_name} (@{user.username})
                      {user.is_online ? ' 🟢' : ' ⚫'}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>

              <div className="d-grid">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={creating || !selectedUserId}
                >
                  {creating ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-2" />
                      Creating Chat...
                    </>
                  ) : (
                    'Create Chat'
                  )}
                </Button>
              </div>
            </Form>
          </Card.Body>
        </Card>
      </div>
    </div>
  );
};

export default CreatePrivateChat;