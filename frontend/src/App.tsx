import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';

// Components
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import ChatList from './components/chat/ChatList';
import ChatDetail from './components/chat/ChatDetail';
import UserSearch from './components/user/UserSearch';
import CreatePrivateChat from './components/chat/CreatePrivateChat';
import CreateGroupChat from './components/chat/CreateGroupChat';
import Navbar from './components/layout/Navbar';

// Context
import { AuthProvider, useAuth } from './context/AuthContext';

// Types
interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" />;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <Navbar />
          <div className="container mt-4">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <ChatList />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/chats"
                element={
                  <ProtectedRoute>
                    <ChatList />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/chat/:conversationId"
                element={
                  <ProtectedRoute>
                    <ChatDetail />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/create-private"
                element={
                  <ProtectedRoute>
                    <CreatePrivateChat />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/create-group"
                element={
                  <ProtectedRoute>
                    <CreateGroupChat />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/search"
                element={
                  <ProtectedRoute>
                    <UserSearch />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </div>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;