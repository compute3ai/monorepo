"use client";

import { useEffect } from "react";
import { TurnkeyProvider, TurnkeyProviderConfig } from "@turnkey/react-wallet-kit";
import "@turnkey/react-wallet-kit/styles.css";
import { AuthProvider } from "../providers/AuthProvider";
import { WalletProvider } from "../contexts/WalletContext";
import { RainbowKitProvider } from "../providers/RainbowKitProvider";

declare global {
  interface Window {
    twemoji?: {
      parse: (element: HTMLElement | string, options?: { folder?: string; ext?: string }) => void;
    };
  }
}

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
  // Parse emojis with Twemoji for cross-platform flag support (Windows Chrome)
  useEffect(() => {
    const parseEmojis = () => {
      if (window.twemoji) {
        window.twemoji.parse(document.body, {
          folder: 'svg',
          ext: '.svg'
        });
      }
    };

    // Initial parse
    parseEmojis();

    // Re-parse on DOM changes (for dynamic content)
    const observer = new MutationObserver(parseEmojis);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => observer.disconnect();
  }, []);

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
