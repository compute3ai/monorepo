"use client"

import { createContext, useContext, useState, ReactNode } from "react"
import { createWalletClient, custom, type WalletClient } from "viem"
import { base } from "viem/chains"

interface WalletContextType {
  walletClient: WalletClient | null
  address: string | null
  isConnected: boolean
  isConnecting: boolean
  error: string | null
  connectWallet: () => Promise<void>
  disconnectWallet: () => void
}

const WalletContext = createContext<WalletContextType | undefined>(undefined)

export function WalletProvider({ children }: { children: ReactNode }) {
  const [walletClient, setWalletClient] = useState<WalletClient | null>(null)
  const [address, setAddress] = useState<string | null>(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connectWallet = async () => {
    try {
      setIsConnecting(true)
      setError(null)

      if (typeof window.ethereum === "undefined") {
        throw new Error("Please install MetaMask or another Ethereum wallet")
      }

      // Get the actual provider (not the proxy)
      // This resolves issues with Phantom's EthProviderProxy
      let provider = window.ethereum

      // If this is Phantom's proxy and Phantom is available, use Phantom directly
      const phantom = (window as unknown as { phantom?: { ethereum?: typeof window.ethereum } }).phantom
      if (phantom?.ethereum) {
        console.log("🦊 Using Phantom wallet provider")
        provider = phantom.ethereum
      }

      // Request account access
      const accounts = (await provider.request({
        method: "eth_requestAccounts",
      })) as string[]

      if (!accounts || accounts.length === 0) {
        throw new Error("No accounts found")
      }

      // Check current network
      const chainId = (await provider.request({ method: "eth_chainId" })) as string
      const baseMainnetChainIdHex = "0x2105" // 8453 in hex

      // Switch to Base mainnet if needed
      if (chainId !== baseMainnetChainIdHex) {
        try {
          await provider.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: baseMainnetChainIdHex }],
          })
        } catch (switchError: any) {
          // This error code indicates that the chain has not been added to MetaMask
          if (switchError.code === 4902) {
            await provider.request({
              method: "wallet_addEthereumChain",
              params: [
                {
                  chainId: baseMainnetChainIdHex,
                  chainName: "Base",
                  nativeCurrency: {
                    name: "Ethereum",
                    symbol: "ETH",
                    decimals: 18,
                  },
                  rpcUrls: ["https://mainnet.base.org"],
                  blockExplorerUrls: ["https://basescan.org"],
                },
              ],
            })
          } else {
            throw switchError
          }
        }
      }

      // Create wallet client with viem using the actual provider (not proxy)
      const client = createWalletClient({
        account: accounts[0] as `0x${string}`,
        chain: base,
        transport: custom(provider),
      })

      setWalletClient(client)
      setAddress(accounts[0])

      // Listen for account changes on the actual provider
      provider.on("accountsChanged", (newAccounts: any) => {
        if (newAccounts.length === 0) {
          disconnectWallet()
        } else {
          setAddress(newAccounts[0])
          // Update client with new account using the same provider
          const newClient = createWalletClient({
            account: newAccounts[0] as `0x${string}`,
            chain: base,
            transport: custom(provider),
          })
          setWalletClient(newClient)
        }
      })

      // Listen for chain changes on the actual provider
      provider.on("chainChanged", () => {
        window.location.reload()
      })
    } catch (err: any) {
      console.error("Error connecting wallet:", err)
      setError(err.message || "Failed to connect wallet")
      setWalletClient(null)
      setAddress(null)
    } finally {
      setIsConnecting(false)
    }
  }

  const disconnectWallet = () => {
    setWalletClient(null)
    setAddress(null)
    setError(null)
  }

  const value: WalletContextType = {
    walletClient,
    address,
    isConnected: !!walletClient && !!address,
    isConnecting,
    error,
    connectWallet,
    disconnectWallet,
  }

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>
}

export function useWallet() {
  const context = useContext(WalletContext)
  if (context === undefined) {
    throw new Error("useWallet must be used within a WalletProvider")
  }
  return context
}
