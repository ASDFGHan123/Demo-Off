import React, { useState, useEffect } from 'react';
import { Form, Button, Card, Alert, Spinner, Row, Col } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { userAPI, chatAPI } from '../../services/api';

interface User {
  user_id: number;
  username: string;
  display_name: string;
  is_online: boolean;
}

const CreateGroupChat: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<number[]>([]);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
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

  const handleUserToggle = (userId: number) => {
    setSelectedUsers(prev =>
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || selectedUsers.length === 0) return;

    setCreating(true);
    setError('');

    try {
      const response = await chatAPI.createGroupChat({
        title: title.trim(),
        member_ids: selectedUsers,
        description: description.trim() || undefined
      });
      navigate(`/chat/${response.data.conversation_id}`);
    } catch (err) {
      setError('Failed to create group chat');
      console.error('Error creating group chat:', err);
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
      <div className="col-md-8 col-lg-6">
        <Card>
          <Card.Header>
            <h3 className="text-center mb-0">Create Group Chat</h3>
          </Card.Header>
          <Card.Body>
            {error && <Alert variant="danger">{error}</Alert>}

            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>Group Title *</Form.Label>
                <Form.Control
                  type="text"
                  placeholder="Enter group name..."
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  maxLength={100}
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Description (Optional)</Form.Label>
                <Form.Control
                  as="textarea"
                  rows={3}
                  placeholder="Enter group description..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Select Members *</Form.Label>
                <div className="border rounded p-3" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                  <Row>
                    {users.map(user => (
                      <Col key={user.user_id} xs={12} sm={6} className="mb-2">
                        <Form.Check
                          type="checkbox"
                          id={`user-${user.user_id}`}
                          label={
                            <div>
                              <strong>{user.display_name}</strong>
                              <br />
                              <small className="text-muted">@{user.username}</small>
                              <span className={`ms-2 ${user.is_online ? 'text-success' : 'text-secondary'}`}>
                                {user.is_online ? '● Online' : '● Offline'}
                              </span>
                            </div>
                          }
                          checked={selectedUsers.includes(user.user_id)}
                          onChange={() => handleUserToggle(user.user_id)}
                        />
                      </Col>
                    ))}
                  </Row>
                </div>
                <Form.Text className="text-muted">
                  Selected: {selectedUsers.length} members
                </Form.Text>
              </Form.Group>

              <div className="d-grid">
                <Button
                  type="submit"
                  variant="success"
                  disabled={creating || !title.trim() || selectedUsers.length === 0}
                >
                  {creating ? (
                    <>
                      <Spinner animation="border" size="sm" className="me-2" />
                      Creating Group...
                    </>
                  ) : (
                    'Create Group Chat'
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

export default CreateGroupChat;