import React, { createContext, useContext, useState, useEffect } from 'react';
import { userAPI } from '../services/api';

const AuthContext = createContext(null);
const USER_STORAGE_KEY = 'user';

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
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [authStorage, setAuthStorage] = useState(sessionStorage);

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
        const { user: storedUser, storage } = getStoredUser();

        if (storedUser) {
            const userData = storedUser;
            setUser(userData);
            setAuthStorage(storage);
            // Fetch profile if user is logged in
            if (userData?.token) {
                fetchProfile(userData.token);
            }
        }
        setLoading(false);
    }, []);

    const login = async (email, password, rememberMe = false) => {
        const data = await userAPI.login(email, password);
        const storage = rememberMe ? localStorage : sessionStorage;
        const userData = {
            token: data.access_token,
            userId: data.user_id,
            email: data.email,
            fullName: data.full_name,
            role: data.role,
            collegeId: data.college_id,
        };

        setUser(userData);
        setAuthStorage(storage);
        persistUser(userData, storage);
        
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
            persistUser(updatedUser, storage);
        }
        
        return userData;
    };

    const setCollege = async (collegeId) => {
        const resp = await userAPI.setCollege(collegeId);
        const updated = { ...(user || {}), collegeId: resp.college_id };
        setUser(updated);
        persistUser(updated, authStorage);
        return updated;
    };

    const signup = async (email, password, fullName, collegeId) => {
        return userAPI.signup(email, password, fullName, collegeId);
    };

    const logout = () => {
        setUser(null);
        setProfile(null);
        setAuthStorage(sessionStorage);
        clearStoredUser();
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
