import React, { createContext, useContext, useState, useEffect } from 'react';
import { userAPI } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchProfile = async (token) => {
        try {
            const profileData = await userAPI.getProfile();
            setProfile(profileData);
            return profileData;
        } catch (error) {
            console.error('Failed to fetch profile:', error);
            return null;
        }
    };

    useEffect(() => {
        const storedUser = localStorage.getItem('user');
        if (storedUser) {
            const userData = JSON.parse(storedUser);
            setUser(userData);
            // Fetch profile if user is logged in
            if (userData?.token) {
                fetchProfile(userData.token);
            }
        }
        setLoading(false);
    }, []);

    const login = async (email, password) => {
        const data = await userAPI.login(email, password);
        const userData = {
            token: data.access_token,
            userId: data.user_id,
            email: data.email,
            fullName: data.full_name,
            role: data.role,
            collegeId: data.college_id,
        };

        setUser(userData);
        localStorage.setItem('user', JSON.stringify(userData));
        
        // Fetch full profile
        const profileData = await fetchProfile(data.access_token);
        if (profileData) {
            // Update user data with profile info
            const updatedUser = {
                ...userData,
                email: profileData.email || userData.email,
                fullName: profileData.full_name || userData.fullName,
                collegeName: profileData.college_name,
            };
            setUser(updatedUser);
            localStorage.setItem('user', JSON.stringify(updatedUser));
        }
        
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
        setProfile(null);
        localStorage.removeItem('user');
    };

    const refreshProfile = async () => {
        if (user?.token) {
            return await fetchProfile(user.token);
        }
        return null;
    };

    return (
        <AuthContext.Provider value={{ user, profile, login, signup, setCollege, logout, loading, refreshProfile }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
