import React from 'react';
import { Navbar as BootstrapNavbar, Nav, Container, Button } from 'react-bootstrap';
import { LinkContainer } from 'react-router-bootstrap';
import { useAuth } from '../../context/AuthContext';

const Navbar: React.FC = () => {
  const { isAuthenticated, user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  return (
    <BootstrapNavbar bg="primary" variant="dark" expand="lg">
      <Container>
        <LinkContainer to="/">
          <BootstrapNavbar.Brand>OffChat</BootstrapNavbar.Brand>
        </LinkContainer>
        <BootstrapNavbar.Toggle aria-controls="basic-navbar-nav" />
        <BootstrapNavbar.Collapse id="basic-navbar-nav">
          <Nav className="me-auto">
            {isAuthenticated ? (
              <>
                <LinkContainer to="/chats">
                  <Nav.Link>Chats</Nav.Link>
                </LinkContainer>
                <LinkContainer to="/search">
                  <Nav.Link>Search Users</Nav.Link>
                </LinkContainer>
              </>
            ) : (
              <>
                <LinkContainer to="/login">
                  <Nav.Link>Login</Nav.Link>
                </LinkContainer>
                <LinkContainer to="/register">
                  <Nav.Link>Register</Nav.Link>
                </LinkContainer>
              </>
            )}
          </Nav>
          {isAuthenticated && (
            <Nav>
              <span className="navbar-text me-3">
                Welcome, {user?.display_name || user?.username}
              </span>
              <Button variant="outline-light" onClick={handleLogout}>
                Logout
              </Button>
            </Nav>
          )}
        </BootstrapNavbar.Collapse>
      </Container>
    </BootstrapNavbar>
  );
};

export default Navbar;