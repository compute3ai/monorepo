"use client"

import { useState, useEffect } from "react"
import { useWallet } from "../contexts/WalletContext"
import { x402Api, updateX402Client } from "../services/x402Api"
import { debugLog } from "../utils/debug"
import { toUsdcUnits } from "../utils/currency"

interface TopUpModalProps {
  isOpen: boolean
  onClose: () => void
  userEmail?: string
  onSuccess: () => void
}

type PaymentMethod = "crypto" | "card"

export function TopUpModal({ isOpen, onClose, userEmail, onSuccess }: TopUpModalProps) {
  const { walletClient, address, isConnected, isConnecting, connectWallet, error: walletError } = useWallet()
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("crypto")
  const [amount, setAmount] = useState<number>(10)
  const [email, setEmail] = useState<string>(userEmail || "")
  const [isProcessing, setIsProcessing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // Update email when userEmail prop changes
  useEffect(() => {
    if (userEmail) {
      setEmail(userEmail)
    }
  }, [userEmail])

  // Update x402 client when wallet changes
  useEffect(() => {
    updateX402Client(walletClient)
  }, [walletClient])

  const minAmount = paymentMethod === "crypto" ? 0.1 : 5
  const maxAmount = 1000

  const handleClose = () => {
    if (!isProcessing) {
      setAmount(10)
      setError(null)
      setSuccess(false)
      onClose()
    }
  }

  const handlePaymentMethodChange = (method: PaymentMethod) => {
    setPaymentMethod(method)
    // Adjust amount if it's below the new minimum
    if (method === "card" && amount < 5) {
      setAmount(5)
    } else if (method === "crypto" && amount < 0.1) {
      setAmount(0.1)
    }
  }

  const handleCryptoPayment = async () => {
    setIsProcessing(true)
    setError(null)

    try {
      // Step 1: Connect wallet if not connected
      if (!isConnected) {
        debugLog("🔄 Step 1: Connecting MetaMask wallet...")
        await connectWallet()
        debugLog("✅ Wallet connected. Please click Pay again to continue.")
        setIsProcessing(false)
        return
      }

      // Step 2: Get auth token
      const authToken = document.cookie
        .split("; ")
        .find(row => row.startsWith("auth_token="))
        ?.split("=")[1]

      if (!authToken) {
        throw new Error("Authentication required. Please log in.")
      }

      // Step 3: Decode JWT to get user_id
      const tokenParts = authToken.split('.')
      if (tokenParts.length !== 3) {
        throw new Error("Invalid token format")
      }

      const payload = JSON.parse(atob(tokenParts[1]))
      const userId = payload.user_id || payload.sub

      if (!userId) {
        throw new Error("User ID not found in token")
      }

      debugLog("🔑 User ID from token:", userId)

      // Step 4: Make x402 payment
      // Convert to USDC units (6 decimals) - $0.10 = 100,000 units
      const usdcUnits = toUsdcUnits(amount)
      debugLog("💳 Initiating x402 payment for $" + amount + " (" + usdcUnits + " USDC units)")
      const result = await x402Api.topUp(usdcUnits, authToken, userId)
      debugLog("✅ Top up successful:", result)

      // Show success
      setSuccess(true)
      setTimeout(() => {
        onSuccess()
        handleClose()
      }, 2000)

    } catch (err: any) {
      debugLog("❌ Payment error:", err)

      // Handle validation errors from FastAPI
      let errorMessage = "Payment failed. Please try again."

      // Check if this is a wallet selection error from Phantom
      if (err.message?.includes("selectExtension") || err.message?.includes("EthProviderProxy")) {
        errorMessage = "Wallet error: Please disable Phantom wallet extension or use MetaMask only."
      } else if (err.response?.data?.detail) {
        if (Array.isArray(err.response.data.detail)) {
          // FastAPI validation errors
          errorMessage = err.response.data.detail.map((e: any) => e.msg).join(", ")
        } else if (typeof err.response.data.detail === 'string') {
          errorMessage = err.response.data.detail
        }
      } else if (err.message) {
        errorMessage = err.message
      }

      setError(errorMessage)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleCardPayment = async () => {
    setIsProcessing(true)
    setError(null)

    try {
      // Get auth token
      const authToken = document.cookie
        .split("; ")
        .find(row => row.startsWith("auth_token="))
        ?.split("=")[1]

      if (!authToken) {
        throw new Error("Authentication required. Please log in.")
      }

      // Create Stripe checkout session
      // Send dollar amount - backend converts to cents
      debugLog("💳 Creating Stripe checkout session for $" + amount)
      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/stripe/top_up`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`,
        },
        body: JSON.stringify({ amount: amount }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Failed to create checkout session: ${response.statusText}`)
      }

      const data = await response.json()
      debugLog("✅ Checkout session created:", data.session_id)

      // Redirect to Stripe checkout
      window.location.href = data.checkout_url

    } catch (err: any) {
      debugLog("❌ Stripe checkout error:", err)
      setError(err.message || "Payment failed. Please try again.")
      setIsProcessing(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (amount < minAmount || amount > maxAmount) {
      setError(`Amount must be between $${minAmount} and $${maxAmount}`)
      return
    }

    if (paymentMethod === "crypto") {
      handleCryptoPayment()
    } else {
      handleCardPayment()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Top Up Balance</h2>
            <button
              onClick={handleClose}
              disabled={isProcessing}
              className="text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {success ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Payment Successful!</h3>
              <p className="text-gray-600">Your balance will be updated shortly.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              {/* Wallet Notice */}
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                <div className="flex items-start">
                  <svg className="w-5 h-5 mr-2 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                  <div>
                    <strong>Note:</strong> If you have both Phantom and MetaMask installed, please disable one of them to avoid payment errors.
                  </div>
                </div>
              </div>

              {/* Payment Method Selection */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-3">Payment Method</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => handlePaymentMethodChange("crypto")}
                    disabled={isProcessing}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      paymentMethod === "crypto"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    } disabled:opacity-50`}
                  >
                    <div className="font-semibold text-gray-900">Crypto</div>
                    <div className="text-xs text-gray-500 mt-1">USDC</div>
                  </button>
                  <button
                    type="button"
                    onClick={() => handlePaymentMethodChange("card")}
                    disabled={isProcessing}
                    className={`p-4 rounded-lg border-2 transition-all ${
                      paymentMethod === "card"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    } disabled:opacity-50`}
                  >
                    <div className="font-semibold text-gray-900">Credit Card</div>
                    <div className="text-xs text-gray-500 mt-1">Stripe</div>
                  </button>
                </div>
              </div>

              {/* Amount Slider */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  Amount: ${amount.toFixed(2)}
                </label>
                <input
                  type="range"
                  min={minAmount}
                  max={maxAmount}
                  step={paymentMethod === "crypto" ? 0.1 : 1}
                  value={amount}
                  onChange={(e) => setAmount(parseFloat(e.target.value))}
                  disabled={isProcessing}
                  className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer slider"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-2">
                  <span>${minAmount}</span>
                  <span>${maxAmount}</span>
                </div>
              </div>


              {/* Error Message */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {error}
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isProcessing}
                className="w-full btn-primary text-white font-semibold py-3 px-6 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isProcessing ? "Processing..." : `Pay $${amount.toFixed(2)}`}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
