const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Get JWT token from localStorage
const getToken = () => {
  const user = localStorage.getItem('user');
  if (user) {
    try {
      const userData = JSON.parse(user);
      return userData.token;
    } catch {
      return null;
    }
  }
  return null;
};

// API request helper
const apiRequest = async (endpoint, options = {}) => {
  const token = getToken();
  
  const config = {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  };

  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

// User APIs
export const userAPI = {
  // Auth
  login: async (email, password) => {
    return apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  signup: async (email, password, fullName, collegeId) => {
    return apiRequest('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name: fullName, college_id: collegeId || null }),
    });
  },

  // College selection (for enabling history)
  getColleges: async () => {
    return apiRequest('/public/colleges');
  },

  setCollege: async (collegeId) => {
    return apiRequest('/user/set-college', {
      method: 'POST',
      body: JSON.stringify({ college_id: collegeId }),
    });
  },

  // Chat
  sendMessage: async (conversationId, userId, collegeId, content) => {
    // If the user is logged in AND has a college_id, send to the main chat endpoint (with history)
    // Otherwise fall back to guest chat (no history) to avoid backend errors.
    if (userId && collegeId) {
      return apiRequest('/chat/', {
        method: 'POST',
        body: JSON.stringify({
          conversation_id: conversationId,
          user_id: userId,
          role: 'user',
          content: content,
        }),
      });
    }

    // Otherwise, use the anonymous guest chat endpoint (no per-user history)
    // Pass collegeId if available (for guest users who selected a college)
    return apiRequest('/guest-chat', {
      method: 'POST',
      body: JSON.stringify({ 
        content,
        college_id: collegeId || null
      }),
    });
  },

  getChatHistory: async (userId) => {
    return apiRequest(`/chat/history/?user_id=${userId}`);
  },

  getConversationMessages: async (conversationId) => {
    return apiRequest(`/chat/conversation/${conversationId}/messages`);
  },

  deleteConversation: async (conversationId) => {
    return apiRequest(`/chat/conversation/${conversationId}`, {
      method: 'DELETE',
    });
  },

  // Notifications
  getNotifications: async (params = {}) => {
    const queryParams = new URLSearchParams();
    if (params.unread_only !== undefined) queryParams.append('unread_only', params.unread_only);
    if (params.notification_type) queryParams.append('notification_type', params.notification_type);
    if (params.limit) queryParams.append('limit', params.limit);
    if (params.offset) queryParams.append('offset', params.offset);
    
    const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
    return apiRequest(`/notifications${query}`);
  },

  markNotificationRead: async (notificationId) => {
    return apiRequest(`/notifications/${notificationId}/read`, {
      method: 'PUT',
    });
  },

  deleteNotification: async (notificationId) => {
    return apiRequest(`/notifications/${notificationId}`, {
      method: 'DELETE',
    });
  },

  getUnreadCount: async () => {
    return apiRequest('/notifications/unread-count');
  },

  // Profile
  getProfile: async () => {
    return apiRequest('/user/profile');
  },
};
