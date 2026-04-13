import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LogIn, UserPlus, Mail, Lock, User, CheckCircle, AlertCircle } from 'lucide-react';

const Login = ({ onSuccess }) => {
    const [mode, setMode] = useState('login');
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [rememberMe, setRememberMe] = useState(false);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const { login, signup } = useAuth();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');
        setIsLoading(true);
        
        try {
            if (mode === 'login') {
                await login(email, password, rememberMe);
                if (onSuccess) onSuccess();
            } else {
                await signup(email, password, fullName, null);
                setSuccessMessage('Account created! Please check your email to confirm your account before logging in.');
                setFullName('');
                setEmail('');
                setPassword('');
                setTimeout(() => {
                    setMode('login');
                    setSuccessMessage('');
                }, 5000);
            }
        } catch (err) {
            setError(err.message || 'Something went wrong, please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="w-full">
            {/* Header */}
            <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl mb-4 shadow-lg">
                    {mode === 'login' ? (
                        <LogIn className="w-8 h-8 text-white" />
                    ) : (
                        <UserPlus className="w-8 h-8 text-white" />
                    )}
                </div>
                <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
                    {mode === 'login' ? 'Welcome Back' : 'Create Account'}
                </h2>
                <p className="text-sm text-slate-600">
                    {mode === 'login'
                        ? 'Sign in to sync your chat history across devices'
                        : 'Sign up to save your conversations and access them later'}
                </p>
            </div>

            {/* Error Message */}
            {error && (
                <div className="mb-4 flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 animate-in fade-in">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" />
                    <span>{error}</span>
                </div>
            )}

            {/* Success Message */}
            {successMessage && (
                <div className="mb-4 flex items-start gap-2 p-3 bg-green-50 border border-green-200 rounded-xl text-sm text-green-700 animate-in fade-in">
                    <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <span>{successMessage}</span>
                </div>
            )}

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'signup' && (
                    <div className="space-y-2">
                        <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                            <User className="w-4 h-4 text-slate-500" />
                            Full name (optional)
                        </label>
                        <input
                            type="text"
                            className="w-full px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:text-slate-400"
                            placeholder="John Doe"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                        />
                    </div>
                )}
                
                <div className="space-y-2">
                    <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                        <Mail className="w-4 h-4 text-slate-500" />
                        Email
                    </label>
                    <input
                        type="email"
                        required
                        className="w-full px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:text-slate-400"
                        placeholder="you@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                </div>
                
                <div className="space-y-2">
                    <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                        <Lock className="w-4 h-4 text-slate-500" />
                        Password
                    </label>
                    <input
                        type="password"
                        required
                        className="w-full px-4 py-3 bg-slate-50 border-2 border-slate-200 rounded-xl focus:outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:text-slate-400"
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />
                </div>

                {mode === 'login' && (
                    <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 transition-colors hover:border-slate-300">
                        <input
                            type="checkbox"
                            checked={rememberMe}
                            onChange={(e) => setRememberMe(e.target.checked)}
                            className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500/30"
                        />
                        <span className="font-medium">Remember me on this device</span>
                    </label>
                )}
                
                <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold shadow-lg hover:shadow-xl transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
                >
                    {isLoading ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            <span>Processing...</span>
                        </>
                    ) : (
                        <>
                            {mode === 'login' ? (
                                <>
                                    <LogIn className="w-4 h-4" />
                                    <span>Sign In</span>
                                </>
                            ) : (
                                <>
                                    <UserPlus className="w-4 h-4" />
                                    <span>Sign Up</span>
                                </>
                            )}
                        </>
                    )}
                </button>
            </form>

            {/* Toggle Mode */}
            <div className="mt-6 pt-6 border-t border-slate-200 text-center">
                <p className="text-sm text-slate-600">
                    {mode === 'login' ? (
                        <>
                            Don&apos;t have an account?{' '}
                                 <button
                                     type="button"
                                     onClick={() => {
                                         setMode('signup');
                                         setRememberMe(false);
                                         setError('');
                                         setSuccessMessage('');
                                     }}
                                className="font-semibold text-blue-600 hover:text-blue-700 hover:underline transition-colors"
                            >
                                Sign up
                            </button>
                        </>
                    ) : (
                        <>
                            Already have an account?{' '}
                                 <button
                                     type="button"
                                     onClick={() => {
                                         setMode('login');
                                         setRememberMe(false);
                                         setError('');
                                         setSuccessMessage('');
                                     }}
                                className="font-semibold text-blue-600 hover:text-blue-700 hover:underline transition-colors"
                            >
                                Log in
                            </button>
                        </>
                    )}
                </p>
            </div>
        </div>
    );
};

export default Login;
