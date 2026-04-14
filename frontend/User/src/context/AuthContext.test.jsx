import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const {
  signupMock,
  loginMock,
  getProfileMock,
  setCollegeMock,
} = vi.hoisted(() => ({
  signupMock: vi.fn(),
  loginMock: vi.fn(),
  getProfileMock: vi.fn(),
  setCollegeMock: vi.fn(),
}));

vi.mock('../services/api', () => ({
  userAPI: {
    signup: signupMock,
    login: loginMock,
    getProfile: getProfileMock,
    setCollege: setCollegeMock,
  },
}));

import { AuthProvider, useAuth } from './AuthContext';

function AuthProbe() {
  const { signup, user, loading } = useAuth();

  const handleSignup = async () => {
    await signup('new@college.edu', 'password123', 'New Student', null);
  };

  return (
    <div>
      <div data-testid="loading-state">{loading ? 'loading' : 'ready'}</div>
      <div data-testid="user-email">{user?.email ?? 'anonymous'}</div>
      <button type="button" onClick={handleSignup}>
        Sign up
      </button>
    </div>
  );
}

describe('AuthProvider signup flow', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    signupMock.mockReset();
    loginMock.mockReset();
    getProfileMock.mockReset();
    setCollegeMock.mockReset();
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('does not auto-login or persist a user after signup', async () => {
    signupMock.mockResolvedValue({
      message:
        'Signup successful! Please check your email to confirm your account before logging in.',
      email_sent: true,
    });
    loginMock.mockResolvedValue({
      access_token: 'unexpected-token',
      user_id: 'user-1',
      email: 'new@college.edu',
      full_name: 'New Student',
      role: 'student',
      college_id: null,
    });

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toHaveTextContent('ready');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }));

    await waitFor(() => {
      expect(signupMock).toHaveBeenCalledWith(
        'new@college.edu',
        'password123',
        'New Student',
        null
      );
    });

    expect(loginMock).not.toHaveBeenCalled();
    expect(localStorage.getItem('user')).toBeNull();
    expect(sessionStorage.getItem('user')).toBeNull();
    expect(screen.getByTestId('user-email')).toHaveTextContent('anonymous');
  });
});
