import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const USER_STORAGE_KEY = 'super_admin_user';

const getStoredUser = () => {
    const storages = [localStorage, sessionStorage];

    for (const storage of storages) {
        const storedUser = storage.getItem(USER_STORAGE_KEY);
        if (!storedUser) {
            continue;
        }

        try {
            return {
                user: JSON.parse(storedUser),
                storage,
            };
        } catch {
            storage.removeItem(USER_STORAGE_KEY);
        }
    }

    return { user: null, storage: sessionStorage };
};

const clearStoredUser = () => {
    localStorage.removeItem(USER_STORAGE_KEY);
    sessionStorage.removeItem(USER_STORAGE_KEY);
};

const persistUser = (userData, storage) => {
    clearStoredUser();
    storage.setItem(USER_STORAGE_KEY, JSON.stringify(userData));
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const { user: storedUser } = getStoredUser();
        if (storedUser) {
            setUser(storedUser);
        }
        setLoading(false);
    }, []);

    const login = async (email, password, rememberMe = false) => {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        
        // Only allow super_admin role
        if (data.role !== 'super_admin') {
            throw new Error('Access denied. Super admin access required.');
        }

        const userData = {
            token: data.access_token,
            userId: data.user_id,
            role: data.role,
            collegeId: data.college_id,
        };

        const storage = rememberMe ? localStorage : sessionStorage;
        setUser(userData);
        persistUser(userData, storage);
        return userData;
    };

    const logout = () => {
        setUser(null);
        clearStoredUser();
    };

    const apiCall = async (endpoint, options = {}) => {
        if (!user?.token) {
            throw new Error('Not authenticated');
        }

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${user.token}`,
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Request failed');
        }

        return response.json();
    };

    return (
        <AuthContext.Provider value={{ user, login, logout, loading, apiCall }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
