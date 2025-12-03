"use client";

import { TurnkeyProvider, TurnkeyProviderConfig } from "@turnkey/react-wallet-kit";
import "@turnkey/react-wallet-kit/styles.css";
import { AuthProvider } from "../providers/AuthProvider";
import { WalletProvider } from "../contexts/WalletContext";
import { RainbowKitProvider } from "../providers/RainbowKitProvider";

const turnkeyConfig: TurnkeyProviderConfig = {
  organizationId: process.env.NEXT_PUBLIC_ORGANIZATION_ID!,
  authProxyConfigId: process.env.NEXT_PUBLIC_AUTH_PROXY_CONFIG_ID!,
};

console.log("🔑 Turnkey Config:", {
  organizationId: turnkeyConfig.organizationId,
  authProxyConfigId: turnkeyConfig.authProxyConfigId,
  hasOrgId: !!turnkeyConfig.organizationId,
  hasProxyId: !!turnkeyConfig.authProxyConfigId,
});

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <RainbowKitProvider>
      <TurnkeyProvider
        config={turnkeyConfig}
        callbacks={{
          onError: (error) => {
            console.error("Turnkey error:", {
              message: error.message,
              code: error.code,
              cause: error.cause,
            });
          },
          onAuthenticationSuccess: ({ session, action, method }) => {
            console.log("✅ Authentication successful!", {
              action,
              method,
              userId: session?.userId,
              organizationId: session?.organizationId,
            });
          },
        }}
      >
        <AuthProvider>
          <WalletProvider>
            {children}
          </WalletProvider>
        </AuthProvider>
      </TurnkeyProvider>
    </RainbowKitProvider>
  );
}
