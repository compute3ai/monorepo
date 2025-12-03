'use client';

import React, { useEffect, useState } from 'react';
import { useTurnkey, AuthState } from '@turnkey/react-wallet-kit';
import { cookieUtils } from '../utils/cookies';

export interface BackendUser {
  id: string;
  email?: string;
  name?: string;
  handle?: string;
}

export function AuthConnect() {
  const { handleLogin, authState, user, logout } = useTurnkey();
  const [backendUser, setBackendUser] = useState<BackendUser | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Detect when session is set and authenticate with backend
  useEffect(() => {
    let hasAttemptedLogin = false;

    const authenticateWithBackend = async () => {
      const sessionData = localStorage.getItem('@turnkey/session/v3');
      if (!sessionData || hasAttemptedLogin) return;

      // Check if we already have a valid JWT (cookies only)
      const existingJwt = cookieUtils.get('jwt_token');
      if (existingJwt) {
        // Try to fetch user profile with existing JWT
        try {
          const profileResponse = await fetch(
            `${process.env.NEXT_PUBLIC_API_BASE}/user`,
            {
              method: 'GET',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${existingJwt}`,
              },
            }
          );

          if (profileResponse.ok) {
            const userData = await profileResponse.json();
            console.log('✅ User profile loaded from existing JWT:', userData);
            setBackendUser(userData);
            setLoginError(null);
            hasAttemptedLogin = true;
            return;
          }
        } catch (error) {
          console.log('Existing JWT invalid, getting new one...');
          cookieUtils.remove('jwt_token');
        }
      }

      hasAttemptedLogin = true;

      try {
        const session = JSON.parse(sessionData);
        console.log('Turnkey session detected, exchanging for JWT...');

        // Step 1: Exchange Turnkey token for our JWT (30 day token)
        const loginResponse = await fetch(`${process.env.NEXT_PUBLIC_API_BASE}/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token: session.token,
          }),
        });

        if (!loginResponse.ok) {
          const error = await loginResponse.json();
          throw new Error(error.detail || 'Authentication failed');
        }

        const { token: jwtToken, expires_in } = await loginResponse.json();
        console.log(`✅ JWT received (expires in ${expires_in}s)`);

        // Store JWT token in cookie (cross-domain)
        cookieUtils.set('jwt_token', jwtToken, 365);

        // Step 2: Fetch user profile with JWT
        const profileResponse = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE}/user`,
          {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${jwtToken}`,
            },
          }
        );

        if (!profileResponse.ok) {
          const error = await profileResponse.json();
          throw new Error(error.detail || 'Failed to fetch profile');
        }

        const userData = await profileResponse.json();
        console.log('✅ User profile loaded:', userData);
        setBackendUser(userData);
        setLoginError(null);
      } catch (error) {
        console.error('❌ Backend authentication failed:', error);
        setLoginError(error instanceof Error ? error.message : 'Authentication failed');
        cookieUtils.remove('jwt_token');
      }
    };

    // Check on mount
    authenticateWithBackend();

    // Listen for storage changes (when session is set)
    window.addEventListener('storage', authenticateWithBackend);

    // Also poll for changes in same window (storage event doesn't fire in same window)
    const interval = setInterval(authenticateWithBackend, 500);

    return () => {
      window.removeEventListener('storage', authenticateWithBackend);
      clearInterval(interval);
    };
  }, []);

  const handleDisconnect = () => {
    // Clear backend user state
    setBackendUser(null);
    setLoginError(null);

    // Clear JWT token (cookie only)
    cookieUtils.remove('jwt_token');

    // Clear all Turnkey session data from localStorage
    localStorage.removeItem('@turnkey/active-session-key');
    localStorage.removeItem('@turnkey/all-session-keys');
    localStorage.removeItem('@turnkey/session/v3');

    // Clear any IndexedDB entries (Turnkey uses IndexedDB for session storage)
    if (window.indexedDB) {
      window.indexedDB.deleteDatabase('turnkey');
    }

    // Call Turnkey logout
    logout();

    // Reload the page to reset state
    window.location.reload();
  };

  if (authState === AuthState.Authenticated) {
    const displayName = backendUser?.name || backendUser?.handle || backendUser?.email || 'User';

    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-3 px-4 py-2 bg-white/5 border border-white/10 rounded-full backdrop-blur-sm">
          <span className="text-sm text-white font-medium">
            {displayName}
          </span>
          <button
            onClick={handleDisconnect}
            className="px-3 py-1 bg-white/10 hover:bg-white/15 border border-white/20 rounded-full text-xs text-white transition-all"
          >
            Disconnect
          </button>
        </div>
        {loginError && (
          <div className="text-red-400 text-sm">{loginError}</div>
        )}
      </div>
    );
  }

  return (
    <div>
      <button
        onClick={() => handleLogin()}
        className="px-6 py-2.5 bg-gradient-to-r from-[var(--color-primary)] to-[var(--color-secondary)] text-white rounded-full font-semibold transition-all hover:scale-105 hover:shadow-lg hover:shadow-orange-500/30"
      >
        Login
      </button>
    </div>
  );
}
