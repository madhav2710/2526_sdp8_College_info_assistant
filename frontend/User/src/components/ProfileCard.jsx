import React, { useState } from "react";
import { Building2, ChevronDown, LogOut, Mail, Shield, User } from "lucide-react";

import { useAuth } from "../context/AuthContext";

const ProfileCard = () => {
  const { user, profile, logout } = useAuth();
  const [isExpanded, setIsExpanded] = useState(false);

  const displayName = profile?.full_name || user?.fullName || "User";
  const displayEmail = profile?.email || user?.email || "No email";
  const displayRole = profile?.role || user?.role || "guest";
  const collegeName = profile?.college_name || null;

  const getInitials = (name) => {
    if (!name) return "U";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  };

  const getRoleConfig = (role) => {
    switch (role) {
      case "super_admin":
        return { icon: Shield, label: "Super Admin" };
      case "college_admin":
        return { icon: Building2, label: "College Admin" };
      case "student":
        return { icon: User, label: "Student" };
      default:
        return { icon: User, label: "Guest" };
    }
  };

  const roleConfig = getRoleConfig(displayRole);
  const RoleIcon = roleConfig.icon;

  return (
    <div className="relative">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-3 rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-surface)] px-3 py-2 shadow-[0_1px_2px_rgba(31,31,28,0.06)]"
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--border-soft)] bg-[var(--bg-subtle)] text-sm font-semibold text-[var(--text-primary)]">
          {getInitials(displayName)}
        </div>

        <div className="hidden text-left sm:block">
          <div className="text-sm font-semibold text-[var(--text-primary)] leading-tight">{displayName}</div>
          <div className="text-xs text-[var(--text-muted)]">{roleConfig.label}</div>
        </div>

        <ChevronDown className={`h-4 w-4 text-[var(--text-muted)] transition-transform ${isExpanded ? "rotate-180" : ""}`} />
      </button>

      {isExpanded && (
        <>
          <div className="fixed inset-0 z-[999] bg-transparent" onClick={() => setIsExpanded(false)} />

          <div className="absolute right-0 top-full z-[1000] mt-2 w-80 rounded-[16px] border border-[var(--border-soft)] bg-[var(--bg-surface)] shadow-[0_4px_12px_rgba(31,31,28,0.08)]">
            <div className="border-b border-[var(--border-soft)] px-5 py-4">
              <h3 className="text-base font-semibold text-[var(--text-primary)]">{displayName}</h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)] truncate">{displayEmail}</p>
            </div>

            <div className="space-y-3 px-5 py-4">
              <div className="rounded-[12px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] p-3">
                <div className="type-meta text-[var(--text-muted)]">Role</div>
                <div className="mt-1 flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">
                  <RoleIcon className="h-4 w-4 text-[var(--accent)]" />
                  {roleConfig.label}
                </div>
              </div>

              <div>
                <div className="type-meta text-[var(--text-muted)]">Email</div>
                <div className="mt-1 flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <Mail className="h-4 w-4" />
                  <span className="truncate">{displayEmail}</span>
                </div>
              </div>

              {collegeName && (
                <div>
                  <div className="type-meta text-[var(--text-muted)]">College</div>
                  <div className="mt-1 flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                    <Building2 className="h-4 w-4" />
                    {collegeName}
                  </div>
                </div>
              )}

              <div>
                <div className="type-meta text-[var(--text-muted)]">User ID</div>
                <div className="mt-1 rounded-[10px] border border-[var(--border-soft)] bg-[var(--bg-subtle)] px-2.5 py-2 text-xs font-mono-ui text-[var(--text-secondary)] break-all">
                  {user?.userId || "N/A"}
                </div>
              </div>
            </div>

            <div className="border-t border-[var(--border-soft)] px-5 py-4">
              <button
                onClick={() => {
                  setIsExpanded(false);
                  logout();
                }}
                className="btn-secondary inline-flex w-full items-center justify-center gap-2"
              >
                <LogOut className="h-4 w-4" />
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
