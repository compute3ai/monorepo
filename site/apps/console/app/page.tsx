"use client";

import { WalletAuth, useAuth } from "@compute3/shared-ui";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function ConsolePage() {
  const { isLoading, isAuthenticated, error, flowState } = useAuth();
  const router = useRouter();

  // Redirect to dashboard if authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isLoading, isAuthenticated, router]);

  // Show error state
  if (flowState === 'error' && error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] p-4">
        <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg max-w-md">
          <div className="text-red-500 mb-4">
            <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Login Failed</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="btn-primary text-white font-semibold py-2 px-6 rounded-lg"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Show loading or auth - using main site colors
  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] p-4">
        {isLoading ? (
          <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg max-w-md">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary)] mx-auto mb-4"></div>
            <p className="text-gray-900">Loading...</p>
          </div>
        ) : (
          <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 shadow-lg">
            <WalletAuth
              showTitle={true}
              title="Welcome to Compute3 Console"
              description="Please sign in to continue"
              onAuthSuccess={() => window.location.reload()}
            />
          </div>
        )}
      </div>
    );
  }

  // Show loading while redirecting
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-white via-gray-50 to-[var(--gradient-start)] p-4">
      <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg max-w-md">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary)] mx-auto mb-4"></div>
        <p className="text-gray-900">Redirecting to dashboard...</p>
      </div>
    </div>
  );
}
