const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getStoredUser = () => {
  const storedUser = localStorage.getItem('super_admin_user') || sessionStorage.getItem('super_admin_user');

  if (!storedUser) {
    return null;
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return null;
  }
};

const getToken = () => {
  return getStoredUser()?.token || null;
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

// Superadmin APIs
export const superadminAPI = {
  // Dashboard
  getStats: async () => {
    return apiRequest('/superadmin/stats');
  },

  // Admins
  getAdmins: async (search = '') => {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiRequest(`/superadmin/admins${query}`);
  },

  getAdminById: async (id) => {
    return apiRequest(`/superadmin/admins/${id}`);
  },

  createAdmin: async (adminData) => {
    return apiRequest('/superadmin/admins', {
      method: 'POST',
      body: JSON.stringify(adminData),
    });
  },

  updateAdmin: async (id, adminData) => {
    return apiRequest(`/superadmin/admins/${id}`, {
      method: 'PUT',
      body: JSON.stringify(adminData),
    });
  },

  deleteAdmin: async (id) => {
    return apiRequest(`/superadmin/admins/${id}`, {
      method: 'DELETE',
    });
  },

  toggleAdminStatus: async (id, status) => {
    return apiRequest(`/superadmin/admins/${id}/toggle-status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  },

  // Colleges
  getColleges: async (search = '') => {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiRequest(`/superadmin/colleges${query}`);
  },

  getCollegeById: async (id) => {
    return apiRequest(`/superadmin/colleges/${id}`);
  },

  createCollege: async (collegeData) => {
    return apiRequest('/superadmin/colleges', {
      method: 'POST',
      body: JSON.stringify(collegeData),
    });
  },

  updateCollege: async (id, collegeData) => {
    return apiRequest(`/superadmin/colleges/${id}`, {
      method: 'PUT',
      body: JSON.stringify(collegeData),
    });
  },

  deleteCollege: async (id) => {
    return apiRequest(`/superadmin/colleges/${id}`, {
      method: 'DELETE',
    });
  },

  // Documents
  getDocuments: async (search = '') => {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiRequest(`/superadmin/documents${query}`);
  },

  // Pending Documents (for approval/rejection)
  getPendingDocuments: async () => {
    return apiRequest('/super-admin/pending-documents');
  },

  approveDocument: async (documentId, comments, processSchedule = 'immediate', scheduledAt = null) => {
    return apiRequest('/super-admin/approve-document', {
      method: 'POST',
      body: JSON.stringify({
        document_id: documentId,
        comments,
        process_schedule: processSchedule,
        scheduled_at: processSchedule === 'scheduled' ? scheduledAt : null,
      }),
    });
  },

  rejectDocument: async (documentId, reason) => {
    return apiRequest('/super-admin/reject-document', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, reason }),
    });
  },

  getScheduledDocuments: async () => {
    return apiRequest('/super-admin/scheduled-documents');
  },

  scheduleDocumentProcessing: async (documentId, scheduledAt) => {
    return apiRequest('/super-admin/schedule-document-processing', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId, scheduled_at: scheduledAt }),
    });
  },

  triggerDocumentProcessing: async (documentId) => {
    return apiRequest('/super-admin/trigger-processing', {
      method: 'POST',
      body: JSON.stringify({ document_id: documentId }),
    });
  },
};
