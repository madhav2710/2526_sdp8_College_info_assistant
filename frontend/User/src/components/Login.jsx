import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { userAPI } from '../services/api';
import { Button } from './ui/button';

const Login = ({ onSuccess }) => {
    const [mode, setMode] = useState('login');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [colleges, setColleges] = useState([]);
    const [selectedCollegeId, setSelectedCollegeId] = useState('');
    const [loadingColleges, setLoadingColleges] = useState(false);
    const { login, signup } = useAuth();

    useEffect(() => {
        const fetchColleges = async () => {
            try {
                setLoadingColleges(true);
                const resp = await userAPI.getColleges();
                const list = resp.colleges || [];
                setColleges(list);
                if (list.length > 0) {
                    setSelectedCollegeId(list[0].id);
                }
            } catch (e) {
                setError(e.message || 'Failed to load colleges');
            } finally {
                setLoadingColleges(false);
            }
        };
        if (mode === 'signup') {
            fetchColleges();
        }
    }, [mode]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        try {
            if (mode === 'login') {
                await login(email, password);
            } else {
                await signup(email, password, fullName, selectedCollegeId);
            }
            // Close modal on success
            if (onSuccess) onSuccess();
        } catch (err) {
            setError(err.message || 'Something went wrong, please try again.');
        }
    };

    return (
        <div>
            <h2 className="mb-2 text-center text-2xl font-bold text-slate-800">
                {mode === 'login' ? 'CollegeInfo Login' : 'Create an Account'}
            </h2>
            <p className="mb-4 text-center text-sm text-slate-500">
                {mode === 'login'
                    ? 'Sign in to sync your chat history across devices.'
                    : 'Sign up to save your conversations and access them later.'}
            </p>
            {error && (
                <div className="mb-4 rounded bg-red-50 p-3 text-sm text-red-500">
                    {error}
                </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'signup' && (
                    <>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Full name (optional)
                            </label>
                            <input
                                type="text"
                                className="mt-1 w-full rounded-md border border-slate-300 p-2 focus:border-blue-500 focus:outline-none"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-700">
                                Select your college
                            </label>
                            <select
                                required
                                className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm focus:border-blue-500 focus:outline-none"
                                value={selectedCollegeId}
                                onChange={(e) => setSelectedCollegeId(e.target.value)}
                            >
                                {loadingColleges && <option value="">Loading colleges...</option>}
                                {!loadingColleges && colleges.length === 0 && (
                                    <option value="">No colleges available</option>
                                )}
                                {colleges.map((c) => (
                                    <option key={c.id} value={c.id}>
                                        {c.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </>
                )}
                <div>
                    <label className="block text-sm font-medium text-slate-700">Email</label>
                    <input
                        type="email"
                        required
                        className="mt-1 w-full rounded-md border border-slate-300 p-2 focus:border-blue-500 focus:outline-none"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-slate-700">Password</label>
                    <input
                        type="password"
                        required
                        className="mt-1 w-full rounded-md border border-slate-300 p-2 focus:border-blue-500 focus:outline-none"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />
                </div>
                <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700">
                    {mode === 'login' ? 'Sign In' : 'Sign Up'}
                </Button>
            </form>
            <div className="mt-4 text-center text-sm text-slate-600">
                {mode === 'login' ? (
                    <>
                        Don&apos;t have an account?{' '}
                        <button
                            type="button"
                            onClick={() => setMode('signup')}
                            className="font-semibold text-blue-600 hover:underline"
                        >
                            Sign up
                        </button>
                    </>
                ) : (
                    <>
                        Already have an account?{' '}
                        <button
                            type="button"
                            onClick={() => setMode('login')}
                            className="font-semibold text-blue-600 hover:underline"
                        >
                            Log in
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

export default Login;
