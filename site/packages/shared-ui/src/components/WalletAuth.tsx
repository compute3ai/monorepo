"use client";

import { useState, useEffect, useRef } from 'react';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import { useAccount, useSignMessage, useDisconnect } from 'wagmi';
import { useTurnkey } from '@turnkey/react-wallet-kit';
import { cookieUtils } from '../utils/cookies';

interface WalletAuthProps {
  onAuthSuccess?: (jwt: string, userId: string) => void;
  showTitle?: boolean; // Show the "Compute3 Chat" title and description
  title?: string; // Custom title (defaults to "Compute3 Chat")
  description?: string; // Custom description
}

type WalletAuthState = 'idle' | 'connected' | 'authenticating' | 'authenticated' | 'error';

const DEBUG = true;
const debugLog = (...args: any[]) => {
  if (DEBUG) {
    console.log('[WalletAuth]', ...args);
  }
};

export function WalletAuth({
  onAuthSuccess,
  showTitle = true,
  title = "Compute3 Chat",
  description = "Choose how you want to sign in"
}: WalletAuthProps) {
  const { address, isConnected } = useAccount();
  const { signMessageAsync } = useSignMessage();
  const { disconnect } = useDisconnect();
  const { handleLogin } = useTurnkey();

  const [authState, setAuthState] = useState<WalletAuthState>('idle');
  const [error, setError] = useState<string | null>(null);
  const processedAddressRef = useRef<string | null>(null);

  // Debug state changes
  useEffect(() => {
    debugLog(`State: ${authState}, isConnected: ${isConnected}, address: ${address}`);
  }, [authState, isConnected, address]);

  // If wallet disconnects, reset to idle
  useEffect(() => {
    if (!isConnected && authState !== 'idle') {
      debugLog('❌ Wallet disconnected, resetting to idle');
      setAuthState('idle');
      processedAddressRef.current = null;
      setError(null);
    }
  }, [isConnected, authState]);

  const handleWalletChallenge = async (walletAddress: string) => {
    // Guard: Don't start if already authenticating or authenticated
    if (authState === 'authenticating' || authState === 'authenticated') {
      debugLog('⚠️ Skipping auth - already in progress/complete:', authState);
      return;
    }

    debugLog('🔄 Starting authentication flow');
    setAuthState('authenticating');
    setError(null);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_BASE!;

      // Step 1: Get challenge from backend
      debugLog('📡 Step 1: Fetching challenge from backend...');
      const challengeRes = await fetch(`${apiUrl}/auth/wallet/challenge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet: walletAddress })
      });

      if (!challengeRes.ok) {
        throw new Error('Failed to get challenge');
      }

      const { timestamp, message } = await challengeRes.json();
      debugLog('✅ Step 1 complete: Challenge received', { timestamp });

      // Step 2: Sign message with wallet
      debugLog('✍️ Step 2: Requesting signature from wallet...');
      const signature = await signMessageAsync({ message });
      debugLog('✅ Step 2 complete: Signature received');

      // Step 3: Verify signature and get JWT
      debugLog('🔐 Step 3: Verifying signature with backend...');
      const verifyRes = await fetch(`${apiUrl}/auth/wallet/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // Include cookies
        body: JSON.stringify({
          wallet: walletAddress,
          signature,
          timestamp: timestamp
        })
      });

      if (!verifyRes.ok) {
        throw new Error('Signature verification failed');
      }

      const loginData = await verifyRes.json();
      debugLog('✅ Step 3 complete: Auth successful!', { user_id: loginData.user_id, tier: loginData.tier });

      // Set auth_token cookie client-side (same as Turnkey flow)
      if (loginData.token) {
        const expiresIn = loginData.expires_in || (parseInt(process.env.NEXT_PUBLIC_COOKIE_VALIDITY || '15') * 24 * 60 * 60);
        cookieUtils.setWithMaxAge('auth_token', loginData.token, expiresIn);
        debugLog('🍪 Cookie set: auth_token');
      }

      debugLog('🎉 Transitioning: authenticating -> authenticated');
      setAuthState('authenticated');

      if (onAuthSuccess) {
        onAuthSuccess(loginData.token, loginData.user_id);
      }

    } catch (err) {
      debugLog('❌ Auth failed:', err);
      setError(err instanceof Error ? err.message : 'Authentication failed');
      debugLog('🔄 Transitioning: authenticating -> error');
      setAuthState('error');
      disconnect();
    }
  };

  const handleTurnkeyLogin = async () => {
    try {
      await handleLogin({
        logoLight: "/favicon.svg",
        logoDark: "/favicon.svg",
        title: "Welcome to Compute3",
      });
    } catch (error) {
      console.error('Turnkey login error:', error);
      setError('Email login failed');
    }
  };

  return (
    <div className="flex flex-col items-center gap-6 w-full max-w-md">
      {showTitle && (
        <div className="text-center">
          <h1 className="text-3xl font-bold text-[var(--color-primary)] mb-2">{title}</h1>
          <p className="text-[var(--color-text)] opacity-70">{description}</p>
        </div>
      )}

      {error && (
        <div className="w-full p-3 rounded-lg bg-red-500 bg-opacity-10 border border-red-500 border-opacity-30">
          <p className="text-sm text-red-500">{error}</p>
        </div>
      )}

      <div className="flex flex-col gap-4 w-full">
        {/* RainbowKit Wallet Connection */}
        <div className="w-full">
          {isConnected && address ? (
            // Wallet is connected - show sign in button
            <button
              onClick={() => handleWalletChallenge(address)}
              disabled={authState === 'authenticating' || authState === 'authenticated'}
              className="w-full btn-primary text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50"
            >
              {authState === 'authenticating' ? 'Signing...' :
               authState === 'authenticated' ? 'Authenticated ✓' :
               'Sign In with Wallet'}
            </button>
          ) : (
            // Wallet not connected - show connect button
            <ConnectButton.Custom>
              {({ openConnectModal, mounted }) => {
                return (
                  <button
                    onClick={openConnectModal}
                    disabled={!mounted}
                    className="w-full btn-primary text-white px-6 py-3 rounded-lg font-medium disabled:opacity-50"
                  >
                    Connect Wallet
                  </button>
                );
              }}
            </ConnectButton.Custom>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-[var(--color-border)]" />
          <span className="text-sm text-[var(--color-text)] opacity-50">or</span>
          <div className="flex-1 h-px bg-[var(--color-border)]" />
        </div>

        {/* Turnkey Email Login */}
        <button
          onClick={handleTurnkeyLogin}
          className="w-full border border-[var(--color-primary)] text-[var(--color-primary)] px-6 py-3 rounded-lg font-medium hover:bg-[var(--color-primary)] hover:text-white transition-colors"
        >
          Login with Email
        </button>
      </div>

      <p className="text-xs text-[var(--color-text)] opacity-50 text-center">
        New users start with a free tier. Top up to unlock more features.
      </p>
    </div>
  );
}
