import React, { createContext, useContext, useState, useEffect } from 'react';
import { userAPI } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            setUser(JSON.parse(storedUser));
        }
        setLoading(false);
    }, []);

    const login = async (email, password) => {
        const data = await userAPI.login(email, password);
        const userData = {
            token: data.access_token,
            userId: data.user_id,
            role: data.role,
            collegeId: data.college_id,
        };

        setUser(userData);
        localStorage.setItem('user', JSON.stringify(userData));
        return userData;
    };

    const setCollege = async (collegeId) => {
        const resp = await userAPI.setCollege(collegeId);
        const updated = { ...(user || {}), collegeId: resp.college_id };
        setUser(updated);
        localStorage.setItem('user', JSON.stringify(updated));
        return updated;
    };

    const signup = async (email, password, fullName, collegeId) => {
        // Create the account first
        await userAPI.signup(email, password, fullName, collegeId);
        // Then log in to obtain token and user info
        return login(email, password);
    };

    const logout = () => {
        setUser(null);
        localStorage.removeItem('user');
    };

    return (
        <AuthContext.Provider value={{ user, login, signup, setCollege, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
