"use client"

import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useState } from "react"
import { useTurnkey } from "@turnkey/react-wallet-kit"
import { cookieUtils } from "../utils/cookies"

// Common loading component - using main site colors
const LoadingCard = ({ message }: { message: string }) => (
  <div className="w-full max-w-md mx-auto">
    <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary)] mx-auto mb-4"></div>
      <p className="text-gray-900">{message}</p>
    </div>
  </div>
)

function AuthContent() {
  const {
    handleLogin,
    logout,
    user,
    session,
  } = useTurnkey()

  // FSM state management
  type AuthState =
    | 'initializing'
    | 'checking_auth'
    | 'auth_proxy_login'
    | 'unauthenticated'
    | 'authenticating'
    | 'authenticated'
    | 'complete'
    | 'redirect'

  const [authState, setAuthState] = useState<AuthState>('initializing')
  const [loginModalShown, setLoginModalShown] = useState(false)

  const router = useRouter()
  const searchParams = useSearchParams()

  // Handle logout
  const handleLogout = async () => {
    // Clear auth cookie
    cookieUtils.remove('auth_token')

    // Call Turnkey logout
    if (logout) {
      await logout()
    }

    // Reset state
    setLoginModalShown(false)
    setAuthState('unauthenticated')
  }

  // FSM Controller
  useEffect(() => {
    const runStateMachine = async () => {
      const redirectParam = searchParams.get('redirect')

      switch (authState) {
        case 'initializing':
          setAuthState('checking_auth')
          break

        case 'checking_auth':
          // Check for authentication - only need auth_token
          const authToken = cookieUtils.get('auth_token')

          console.log('🔍 AUTH CHECK - Checking auth cookies:', {
            user: !!user,
            session: !!session,
            authToken: !!authToken,
          })

          // If we have auth token, user is already authenticated
          if (authToken) {
            console.log('✅ AUTH CHECK - Auth token found, user is authenticated')
            setAuthState('complete')
          } else if (user || session) {
            // We have user/session but missing token, go through auth login flow
            console.log('⚠️ AUTH CHECK - Found user/session but missing token, logging in...')
            setAuthState('auth_proxy_login')
          } else {
            console.log('❌ AUTH CHECK - No auth found, showing login')
            setAuthState('unauthenticated')
          }
          break

        case 'auth_proxy_login':
          // Login with Turnkey session and get JWT token
          if (session?.token) {
            try {
              const loginRes = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: session.token }),
              })
              const loginData = await loginRes.json()

              if (loginData.token) {
                // Use expires_in from response, fallback to env var
                const expiresIn = loginData.expires_in || (parseInt(process.env.NEXT_PUBLIC_COOKIE_VALIDITY || '15') * 24 * 60 * 60)
                cookieUtils.setWithMaxAge('auth_token', loginData.token, expiresIn)
                setAuthState('authenticated')
              } else {
                setAuthState('unauthenticated')
              }
            } catch (error) {
              console.error('Auth login failed:', error)
              setAuthState('unauthenticated')
            }
          } else {
            setAuthState('unauthenticated')
          }
          break

        case 'authenticated':
          setAuthState('complete')
          break

        case 'unauthenticated':
          // Stay in unauthenticated state, waiting for user to click login button
          break

        case 'authenticating':
          // Handle successful authentication
          if (user || session) {
            console.log('🔑 User authenticated, starting auth login flow')
            setAuthState('auth_proxy_login')
          }
          break

        case 'complete':
          // User is authenticated - check if redirect is needed
          if (redirectParam) {
            console.log('✅ COMPLETE - User authenticated, redirect param found:', redirectParam)
            setAuthState('redirect')
          } else {
            console.log('✅ COMPLETE - User authenticated, showing logout option')
            // Stay in complete state to show already logged in UI
          }
          break

        case 'redirect':
          console.log('🚀 REDIRECT - Handling redirect to:', redirectParam)
          setTimeout(() => {
            if (redirectParam?.startsWith('http')) {
              window.location.href = redirectParam
            } else {
              router.push('/dashboard')
            }
          }, 1000)
          break
      }
    }

    runStateMachine()
  }, [authState, user, session, router, searchParams, handleLogin, loginModalShown])

  // Watch for user/session changes to trigger auth flow
  useEffect(() => {
    if ((user || session) && authState === 'unauthenticated') {
      setAuthState('authenticating')
    }
  }, [user, session, authState])

  // Handle FSM states
  if (authState === 'initializing' || authState === 'checking_auth') {
    return <LoadingCard message="Checking authentication..." />
  }

  if (authState === 'auth_proxy_login') {
    return <LoadingCard message="Logging you in..." />
  }

  if (authState === 'redirect') {
    return <LoadingCard message="Redirecting..." />
  }

  if (authState === 'unauthenticated' || authState === 'authenticating') {
    // Turnkey modal is shown via handleLogin() in the useEffect
    return (
      <div className="w-full max-w-md mx-auto">
        <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg">
          <div className="flex justify-center mb-4">
            <img src="/favicon.svg" alt="Compute3" className="h-16 w-16" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Welcome to Compute3
          </h2>
          <p className="text-gray-600 text-sm mb-6">
            Sign in to access your account
          </p>
          <button
            onClick={async () => {
              if (handleLogin) {
                setLoginModalShown(true)
                try {
                  await handleLogin({
                    logoLight: "/favicon.svg",
                    logoDark: "/favicon.svg",
                    title: "Welcome to Compute3",
                  })
                  setAuthState('authenticating')
                } catch (error) {
                  console.error('Login modal error:', error)
                  setLoginModalShown(false)
                }
              }
            }}
            className="btn-primary w-full h-12 px-4 py-2 text-white font-medium rounded-lg"
          >
            Open Login
          </button>
        </div>
      </div>
    )
  }

  if (authState === 'complete') {
    // User is already logged in - show options to go to dashboard or logout
    return (
      <div className="w-full max-w-md mx-auto">
        <div className="glassmorphism bg-white/95 border border-gray-200 rounded-2xl p-8 text-center shadow-lg">
          <div className="flex justify-center mb-4">
            <img src="/favicon.svg" alt="Compute3" className="h-16 w-16" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            You're Already Logged In
          </h2>
          <p className="text-gray-600 text-sm mb-6">
            You're currently authenticated with Compute3.
          </p>
          <div className="space-y-3">
            <button
              onClick={() => router.push('/dashboard')}
              className="btn-primary w-full h-12 px-4 py-2 text-white font-medium rounded-lg"
            >
              Go to Dashboard
            </button>
            <button
              onClick={handleLogout}
              className="btn-secondary w-full h-12 px-4 py-2 text-gray-900 font-medium rounded-lg"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    )
  }

  // For authenticated or unknown states, render nothing
  return null
}

export default function Auth() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AuthContent />
    </Suspense>
  )
}
