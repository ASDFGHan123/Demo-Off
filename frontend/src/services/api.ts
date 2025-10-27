import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add CSRF token
api.interceptors.request.use((config) => {
  const csrfToken = getCsrfToken();
  if (csrfToken) {
    config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});

function getCsrfToken(): string | null {
  const csrfToken = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
  return csrfToken || null;
}

// Auth API
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/login/', { username, password }, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }),

  register: (userData: any) =>
    api.post('/api/auth/register/', userData),

  logout: () => api.post('/logout/'),

  getCurrentUser: () => api.get('/api/users/me/'),
};

// Chat API
export const chatAPI = {
  getConversations: () => api.get('/api/conversations/'),

  getConversation: (id: number) => api.get(`/api/conversations/${id}/`),

  getMessages: (conversationId: number) => api.get(`/api/conversations/${conversationId}/messages/`),

  sendMessage: (conversationId: number, content: string, replyTo?: number) =>
    api.post(`/chat/${conversationId}/send/`, { content, reply_to: replyTo }),

  createPrivateChat: (userId: number) =>
    api.post('/api/create-private-chat/', { user_id: userId }),

  createGroupChat: (data: { title: string; member_ids: number[]; description?: string }) =>
    api.post('/api/create-group-chat/', data),

  searchMessages: (query: string) =>
    api.get('/api/search/messages/', { params: { q: query } }),
};

// User API
export const userAPI = {
  searchUsers: (query: string) => api.get('/search/', { params: { q: query } }),

  getUsers: () => api.get('/api/users/'),

  getUser: (id: number) => api.get(`/api/users/${id}/`),

  updateUser: (id: number, data: any) => api.put(`/api/users/${id}/`, data),
};

// File upload API
export const fileAPI = {
  uploadAttachment: (file: File, messageId: number) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('message_id', messageId.toString());

    return api.post('/upload-attachment/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
};

export default api;