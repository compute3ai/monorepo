"use client";

import '@rainbow-me/rainbowkit/styles.css';
import { RainbowKitProvider as RKProvider, getDefaultConfig } from '@rainbow-me/rainbowkit';
import { WagmiProvider, createConfig, http } from 'wagmi';
import { base, baseSepolia } from 'wagmi/chains';
import { QueryClientProvider, QueryClient } from '@tanstack/react-query';
import { ReactNode } from 'react';

const queryClient = new QueryClient();

const walletConnectProjectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID;

// Full config with WalletConnect if project ID is set
const fullConfig = walletConnectProjectId
  ? getDefaultConfig({
      appName: 'Compute3',
      projectId: walletConnectProjectId,
      chains: [base, baseSepolia],
      ssr: true,
    })
  : null;

// Minimal config without WalletConnect for when project ID is not set
const minimalConfig = createConfig({
  chains: [base, baseSepolia],
  transports: {
    [base.id]: http(),
    [baseSepolia.id]: http(),
  },
  ssr: true,
});

const config = fullConfig || minimalConfig;

export function RainbowKitProvider({ children }: { children: ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RKProvider>{children}</RKProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
