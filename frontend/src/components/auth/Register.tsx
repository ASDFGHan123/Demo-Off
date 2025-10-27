import React, { useState } from 'react';
import { Form, Button, Card, Alert, Spinner } from 'react-bootstrap';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const Register: React.FC = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    display_name: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { register } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const success = await register(formData);
      if (success) {
        navigate('/chats');
      } else {
        setError('Username already taken or registration failed. Please try a different username.');
      }
    } catch (err) {
      setError('Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-4">
        <Card>
          <Card.Header>
            <h3 className="text-center mb-0">Register for OffChat</h3>
          </Card.Header>
          <Card.Body>
            {error && <Alert variant="danger">{error}</Alert>}
            <Form onSubmit={handleSubmit}>
              <Form.Group className="mb-3">
                <Form.Label>Username</Form.Label>
                <Form.Control
                  type="text"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  required
                  placeholder="Choose a username"
                  minLength={3}
                />
                <Form.Text className="text-muted">
                  Minimum 3 characters
                </Form.Text>
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Display Name</Form.Label>
                <Form.Control
                  type="text"
                  name="display_name"
                  value={formData.display_name}
                  onChange={handleChange}
                  required
                  placeholder="Your display name"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Email (Optional)</Form.Label>
                <Form.Control
                  type="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="your@email.com"
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Password</Form.Label>
                <Form.Control
                  type="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  required
                  placeholder="Choose a password"
                  minLength={8}
                />
                <Form.Text className="text-muted">
                  Minimum 8 characters
                </Form.Text>
              </Form.Group>

              <Button
                variant="primary"
                type="submit"
                className="w-100"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Spinner animation="border" size="sm" className="me-2" />
                    Registering...
                  </>
                ) : (
                  'Register'
                )}
              </Button>
            </Form>
          </Card.Body>
          <Card.Footer className="text-center">
            Already have an account? <Link to="/login">Login here</Link>
          </Card.Footer>
        </Card>
      </div>
    </div>
  );
};

export default Register;