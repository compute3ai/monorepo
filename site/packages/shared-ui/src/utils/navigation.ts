/**
 * Navigation utilities for cross-domain navigation
 * Handles navigation between main site and subdomains
 *
 * These values are inlined at BUILD TIME by Next.js webpack.
 * Required env vars are validated in each app's next.config.ts
 */

const MAIN_SITE_URL = process.env.NEXT_PUBLIC_MAIN_SITE_URL!;
const CONSOLE_URL = process.env.NEXT_PUBLIC_CONSOLE_URL!;
const CHAT_URL = process.env.NEXT_PUBLIC_CHAT_URL!;
const IS_MAIN_SITE = process.env.NEXT_PUBLIC_IS_MAIN_SITE === 'true';

/**
 * Get navigation URLs - returns absolute URLs for cross-domain links, relative for same-domain
 * These are determined at BUILD TIME based on NEXT_PUBLIC_IS_MAIN_SITE
 */
export const NAV_URLS = {
  // Home always goes to main site
  home: IS_MAIN_SITE ? '/' : MAIN_SITE_URL,

  // Main site pages
  models: IS_MAIN_SITE ? '/models' : `${MAIN_SITE_URL}/models`,
  gpus: IS_MAIN_SITE ? '/gpus' : `${MAIN_SITE_URL}/gpus`,
  playground: IS_MAIN_SITE ? '/playground' : `${MAIN_SITE_URL}/playground`,
  docs: 'https://docs.compute3.ai',

  // Console pages
  console: `${CONSOLE_URL}/dashboard`,
  launch: `${CONSOLE_URL}/jobs`,
  dashboard: `${CONSOLE_URL}/dashboard`,
  jobs: `${CONSOLE_URL}/jobs`,
  history: `${CONSOLE_URL}/history`,
  keys: `${CONSOLE_URL}/keys`,

  // Chat
  chat: CHAT_URL,
} as const;

/**
 * Get the contact modal trigger (always opens modal, no navigation)
 */
export const openContactModal = (setModalOpen: (open: boolean) => void) => {
  setModalOpen(true);
};
