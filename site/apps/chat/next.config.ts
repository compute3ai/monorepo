import type { NextConfig } from "next";

// Build-time validation of required environment variables
const requiredEnvVars = [
  'NEXT_PUBLIC_MAIN_SITE_URL',
  'NEXT_PUBLIC_CONSOLE_URL',
  'NEXT_PUBLIC_CHAT_URL',
  'NEXT_PUBLIC_COOKIE_DOMAIN',
  'NEXT_PUBLIC_ORGANIZATION_ID',
  'NEXT_PUBLIC_AUTH_PROXY_CONFIG_ID',
  'NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID',
] as const;

for (const envVar of requiredEnvVars) {
  if (!process.env[envVar]) {
    throw new Error(`Missing required environment variable: ${envVar}`);
  }
}

const nextConfig: NextConfig = {
  transpilePackages: ["@compute3/shared-ui"],
  env: {
    // This app is NOT the main site (it's the chat subdomain)
    NEXT_PUBLIC_IS_MAIN_SITE: "false",
  },
};

export default nextConfig;
