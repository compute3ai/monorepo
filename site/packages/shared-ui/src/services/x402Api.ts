import axios from "axios"
import type { AxiosInstance } from "axios"
import type { WalletClient } from "viem"
import { withPaymentInterceptor } from "x402-axios"
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
let currentApiClient: AxiosInstance = baseApiClient

// Update the API client with wallet for x402 payments
export function updateX402Client(walletClient: WalletClient | null) {
  if (walletClient && walletClient.account) {
    debugLog("💳 Wallet client set:", walletClient.account.address)
    debugLog("Wallet chain:", walletClient.chain)
    // Create axios instance with x402 payment interceptor
    currentApiClient = withPaymentInterceptor(baseApiClient, walletClient as any)
  } else {
    debugLog("⚠️ Wallet client cleared")
    // Reset to base client without payment interceptor
    currentApiClient = baseApiClient
  }
}

// x402 API endpoints
export const x402Api = {
  // Paid endpoint - top up balance with USDC
  // The x402-axios interceptor will automatically handle the payment flow
  topUp: async (amount: number, authToken: string, userId: string) => {
    debugLog("💰 Topping up balance via x402:", { amount, userId })

    // Just make a simple POST request - the interceptor will:
    // 1. Get the 402 response with payment requirements
    // 2. Create the payment header using the connected wallet
    // 3. Retry the request with the payment header automatically
    const response = await currentApiClient.post(
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

    debugLog("✅ Top up successful:", response.data)
    return response.data
  },
}
