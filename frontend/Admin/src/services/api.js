const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Get JWT token from localStorage
const getToken = () => {
  const token = localStorage.getItem('admin_token');
  return token;
};

// API request helper
const apiRequest = async (endpoint, options = {}) => {
  const token = getToken();
  
  const config = {
    ...options,
    headers: {
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  };

  // Don't set Content-Type for FormData (file uploads)
  if (!(options.body instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
  }

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

// Admin APIs
export const adminAPI = {
  // Auth
  login: async (email, password) => {
    return apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  // Documents
  getDocuments: async (params = {}) => {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append('status', params.status);
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_order) queryParams.append('sort_order', params.sort_order);
    
    const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
    return apiRequest(`/admin/documents${query}`);
  },

  uploadDocument: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    return apiRequest('/admin/upload', {
      method: 'POST',
      body: formData,
    });
  },

  triggerRagProcessing: async (documentId) => {
    return apiRequest('/admin/trigger-rag-processing', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId }),
    });
  },

  // Query History
  getQueryHistory: async (limit = 10) => {
    return apiRequest(`/admin/query-history?limit=${limit}`);
  },

  deleteQueryHistory: async (conversationId) => {
    return apiRequest(`/admin/query-history/${conversationId}`, {
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
};
