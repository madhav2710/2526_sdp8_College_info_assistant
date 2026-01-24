import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Mail, Building2, Shield, LogOut, ChevronDown } from 'lucide-react';

const ProfileCard = () => {
    const { user, profile, logout } = useAuth();
    const [isExpanded, setIsExpanded] = useState(false);

    // Use profile data if available, otherwise fall back to user data
    const displayName = profile?.full_name || user?.fullName || 'User';
    const displayEmail = profile?.email || user?.email || 'No email';
    const displayRole = profile?.role || user?.role || 'guest';
    const collegeName = profile?.college_name || null;

    // Get initials for avatar
    const getInitials = (name) => {
        if (!name) return 'U';
        const parts = name.trim().split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    };

    // Role badge colors and icons
    const getRoleConfig = (role) => {
        switch (role) {
            case 'super_admin':
                return {
                    color: 'from-purple-500 to-pink-600',
                    badge: 'bg-purple-100 text-purple-700 border-purple-300',
                    icon: Shield,
                    label: 'Super Admin'
                };
            case 'college_admin':
                return {
                    color: 'from-blue-500 to-cyan-600',
                    badge: 'bg-blue-100 text-blue-700 border-blue-300',
                    icon: Building2,
                    label: 'College Admin'
                };
            case 'student':
                return {
                    color: 'from-green-500 to-emerald-600',
                    badge: 'bg-green-100 text-green-700 border-green-300',
                    icon: User,
                    label: 'Student'
                };
            default:
                return {
                    color: 'from-slate-500 to-slate-600',
                    badge: 'bg-gray-100 text-gray-700 border-gray-300',
                    icon: User,
                    label: 'Guest'
                };
        }
    };

    const roleConfig = getRoleConfig(displayRole);
    const RoleIcon = roleConfig.icon;

    return (
        <div className="relative">
            {/* Profile Button */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-3 px-3 py-2 bg-white rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 border border-slate-200/50 group"
            >
                {/* Avatar */}
                <div className="relative">
                    <div className={`w-9 h-9 rounded-xl bg-gradient-to-br ${roleConfig.color} flex items-center justify-center text-white font-bold text-sm shadow-md group-hover:scale-110 transition-transform duration-200`}>
                        {getInitials(displayName)}
                    </div>
                    <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white shadow-sm"></div>
                </div>

                {/* Name and Role - Hidden on mobile */}
                <div className="text-left hidden sm:block">
                    <div className="text-sm font-semibold text-slate-800 leading-tight">{displayName}</div>
                    <div className="text-xs text-slate-500">{roleConfig.label}</div>
                </div>

                {/* Dropdown Icon */}
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
            </button>

            {/* Expanded Profile Card */}
            {isExpanded && (
                <>
                    {/* Backdrop - No blur, just transparent overlay */}
                    <div
                        className="fixed inset-0 z-[999] bg-transparent"
                        onClick={() => setIsExpanded(false)}
                    ></div>

                    {/* Card - High z-index to appear above everything, fully opaque, no blur */}
                    <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-2xl shadow-2xl border-2 border-slate-300 z-[1000] animate-in slide-in-from-top-2 duration-200 overflow-hidden" style={{ backdropFilter: 'none', WebkitBackdropFilter: 'none' }}>
                        {/* Header with gradient */}
                        <div className={`bg-gradient-to-br ${roleConfig.color} p-6 text-white relative overflow-hidden`}>
                            <div className="absolute inset-0 bg-black/10"></div>
                            <div className="relative flex items-center gap-4">
                                <div className={`w-16 h-16 rounded-2xl bg-white/30 flex items-center justify-center text-2xl font-bold border-2 border-white/40 shadow-lg`}>
                                    {getInitials(displayName)}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <h3 className="text-lg font-bold truncate">{displayName}</h3>
                                    <p className="text-sm text-white/90 truncate">{displayEmail}</p>
                                </div>
                            </div>
                        </div>

                        {/* Body - Fully visible, no blur */}
                        <div className="p-5 space-y-4 bg-white" style={{ backdropFilter: 'none', WebkitBackdropFilter: 'none' }}>
                            {/* Role Badge */}
                            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                                <div className="flex items-center gap-2">
                                    <div className={`p-2 rounded-lg bg-gradient-to-br ${roleConfig.color} text-white`}>
                                        <RoleIcon className="w-4 h-4" />
                                    </div>
                                    <span className="text-sm font-medium text-slate-700">Role</span>
                                </div>
                                <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${roleConfig.badge}`}>
                                    {roleConfig.label}
                                </span>
                            </div>

                            {/* Email */}
                            <div className="space-y-2">
                                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex items-center gap-1">
                                    <Mail className="w-3 h-3" />
                                    Email
                                </span>
                                <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                                    <span className="text-sm font-medium text-slate-900 break-all">{displayEmail}</span>
                                </div>
                            </div>

                            {/* College */}
                            {collegeName && (
                                <div className="space-y-2">
                                    <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider flex items-center gap-1">
                                        <Building2 className="w-3 h-3" />
                                        College
                                    </span>
                                    <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-lg">
                                        <span className="text-sm font-medium text-slate-900">{collegeName}</span>
                                    </div>
                                </div>
                            )}

                            {/* User ID */}
                            <div className="space-y-2 pt-2 border-t border-slate-200">
                                <span className="text-xs font-semibold text-slate-600 uppercase tracking-wider">User ID</span>
                                <div className="p-2 bg-slate-50 rounded-lg">
                                    <code className="text-xs text-slate-800 font-mono break-all font-semibold">
                                        {user?.userId || 'N/A'}
                                    </code>
                                </div>
                            </div>
                        </div>

                        {/* Footer - Fully visible, no blur */}
                        <div className="px-5 py-4 bg-gradient-to-r from-slate-50 to-blue-50 border-t border-slate-200" style={{ backdropFilter: 'none', WebkitBackdropFilter: 'none' }}>
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-xs font-semibold text-slate-700">Account Status</span>
                                <span className="flex items-center gap-1.5 text-green-600 font-semibold text-xs">
                                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-sm"></div>
                                    Active
                                </span>
                            </div>
                            <button
                                onClick={() => {
                                    setIsExpanded(false);
                                    logout();
                                }}
                                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-50 hover:bg-red-100 text-red-600 rounded-xl font-semibold text-sm transition-all hover:scale-[1.02] active:scale-[0.98]"
                            >
                                <LogOut className="w-4 h-4" />
                                Sign Out
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default ProfileCard;
