import axios from "axios"
import type { AxiosInstance } from "axios"
import type { WalletClient } from "viem"
import { createPaymentHeader } from "x402/client"
import type { PaymentRequirements } from "x402/types"
import { debugLog } from "../utils/debug"

const API_BASE_URL = process.env.NEXT_PUBLIC_AUTH_BACKEND!;

// Base axios instance without payment interceptor
const baseApiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

// This will be dynamically set based on wallet connection
let currentWalletClient: WalletClient | null = null

// Update the wallet client reference
export function updateX402Client(walletClient: WalletClient | null) {
  currentWalletClient = walletClient

  if (walletClient && walletClient.account) {
    debugLog("💳 Wallet client set:", walletClient.account.address)
    debugLog("Wallet chain:", walletClient.chain)
  } else {
    debugLog("⚠️ Wallet client cleared")
  }
}

// x402 API endpoints
export const x402Api = {
  // Paid endpoint - top up balance with USDC
  // The component specifies the exact amount to pay
  topUp: async (amount: number, authToken: string, userId: string) => {
    debugLog("💰 Topping up balance via x402:", { amount, userId })

    if (!currentWalletClient) {
      throw new Error("Wallet not connected")
    }

    // Step 1: Make initial request to get 402 response with payment requirements
    try {
      await baseApiClient.post(
        "/x402/top_up",
        {
          user_id: userId,
          amount: amount,
        },
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        }
      )
      // If we got here, no payment required (shouldn't happen)
      throw new Error("Expected 402 response but got success")
    } catch (error: any) {
      if (error.response?.status !== 402) {
        debugLog("❌ Unexpected error:", error)
        throw error
      }

      // Step 2: Parse payment requirements from 402 response
      const { x402Version, accepts } = error.response.data as {
        x402Version: number
        accepts: PaymentRequirements[]
      }

      debugLog("💳 Received 402 response with payment requirements:", accepts)

      // Step 3: Select the base/USDC requirement
      const baseRequirement = accepts.find(
        req => req.network === "base" && req.scheme === "exact"
      )

      if (!baseRequirement) {
        throw new Error("No Base network payment requirement found")
      }

      debugLog("💳 Using payment requirement from server:", {
        maxAmountRequired: baseRequirement.maxAmountRequired,
        userRequestedAmount: amount.toString(),
      })

      // Step 4: Create payment header with the user's requested amount
      // The payment authorization will be for the user's amount, but must be <= maxAmountRequired
      const paymentHeader = await createPaymentHeader(
        currentWalletClient as any,
        x402Version,
        baseRequirement
      )

      // Step 5: Retry request with payment header
      const response = await baseApiClient.post(
        "/x402/top_up",
        {
          user_id: userId,
          amount: amount,
        },
        {
          headers: {
            Authorization: `Bearer ${authToken}`,
            "X-PAYMENT": paymentHeader,
            "Access-Control-Expose-Headers": "X-PAYMENT-RESPONSE",
          },
        }
      )

      debugLog("✅ Top up successful:", response.data)
      return response.data
    }
  },
}
