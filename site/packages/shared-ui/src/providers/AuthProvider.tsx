"use client"

import { useTurnkey } from "@turnkey/react-wallet-kit"
import { createContext, ReactNode, useContext, useEffect, useState } from "react"
import { cookieUtils } from "../utils/cookies"

// Debug logging helper - only logs in development
const DEBUG = process.env.NEXT_PUBLIC_AUTH_DEBUG === 'true'
const debugLog = (...args: any[]) => {
  if (DEBUG) {
    console.log(...args)
  }
}

interface UserInfo {
  email?: string
  organizationId?: string
}

interface AuthContextType {
  isLoading: boolean
  userInfo: UserInfo | null
  flowState: string
  error: string | null
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const { user, session, logout } = useTurnkey()
  const [isLoading, setIsLoading] = useState(true)
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
  const [flowState, setFlowState] = useState<'checking_cookies' | 'idle' | 'verifying' | 'complete' | 'error'>('checking_cookies')
  const [error, setError] = useState<string | null>(null)

  // Auth Flow State Machine - check cookies first, then run flow if needed
  useEffect(() => {
    // Step 0: Check if user is already authenticated via cookies
    if (flowState === 'checking_cookies') {
      const authToken = cookieUtils.get('auth_token')

      debugLog('🔍 CHECKING COOKIES - Found:', {
        authToken: !!authToken,
      })

      // If we have auth token, user is already authenticated - skip the flow
      if (authToken) {
        debugLog('✅ Auth token found - user already authenticated, skipping flow')

        // Set up basic info from cookies
        const userEmail = user?.userEmail
        const isValidEmail = userEmail && userEmail.includes('@') && !userEmail.includes('org_')

        setUserInfo({
          email: isValidEmail ? userEmail : undefined,
          organizationId: session?.organizationId || 'N/A',
        })

        setFlowState('complete')
        setIsLoading(false)
      } else {
        // No auth token - check if we have a fresh session to start the flow
        debugLog('❌ Auth token not found')
        if (session?.token) {
          debugLog('🔑 Session found - starting authentication flow')
          setFlowState('verifying')
        } else {
          debugLog('⏸️  No session - waiting for login')
          setFlowState('idle')
          setIsLoading(false)
        }
      }
      return
    }

    // Only start the auth flow if we transition from idle to having a session
    if (flowState === 'idle' && session?.token) {
      debugLog('New login session detected, starting authentication flow...')
      setFlowState('verifying')
    }
  }, [session, flowState, user])

  // Auth Flow Controller
  useEffect(() => {
    if (!session?.token || flowState === 'idle' || flowState === 'checking_cookies') return

    const runAuthFlow = async () => {
      try {
        switch (flowState) {
          case 'verifying':
            debugLog('Logging in with Turnkey session...')
            const loginRes = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/auth/login`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ token: session.token }),
            })

            if (!loginRes.ok) {
              // Handle HTTP errors
              let errorMessage = `Login failed (${loginRes.status})`
              try {
                const errorData = await loginRes.json()
                errorMessage = errorData.detail || errorData.message || errorMessage
              } catch {
                // Response may not be JSON
              }
              console.error('Login error:', errorMessage)
              setError(errorMessage)
              setFlowState('error')
              setIsLoading(false)
              break
            }

            const loginData = await loginRes.json()

            if (loginData.token) {
              // Use expires_in from response, fallback to env var
              const expiresIn = loginData.expires_in || (parseInt(process.env.NEXT_PUBLIC_COOKIE_VALIDITY || '15') * 24 * 60 * 60)
              cookieUtils.setWithMaxAge('auth_token', loginData.token, expiresIn)

              // Set user info
              const userEmail = user?.userEmail
              const isValidEmail = userEmail && userEmail.includes('@') && !userEmail.includes('org_')

              setUserInfo({
                email: isValidEmail ? userEmail : undefined,
                organizationId: session?.organizationId || 'N/A',
              })

              setFlowState('complete')
              setIsLoading(false)
            } else {
              setError('Login failed: No token received')
              setFlowState('error')
              setIsLoading(false)
            }
            break
        }
      } catch (error) {
        console.error('Auth flow error:', error)
        setError(error instanceof Error ? error.message : 'Unknown error')
        setFlowState('error')
        setIsLoading(false)
      }
    }

    runAuthFlow()
  }, [flowState, session, user])

  const isAuthenticated = !isLoading && flowState === 'complete'

  const value: AuthContextType = {
    isLoading,
    userInfo,
    flowState,
    error,
    isAuthenticated
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
