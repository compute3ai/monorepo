/**
 * Cookie utilities for cross-domain authentication
 * Sets cookies on configured domain for use across all subdomains
 *
 * COOKIE_DOMAIN is inlined at BUILD TIME by Next.js webpack.
 * Required env var is validated in each app's next.config.ts
 */

const COOKIE_DOMAIN = process.env.NEXT_PUBLIC_COOKIE_DOMAIN!;

export const cookieUtils = {
  /**
   * Set a cookie with cross-domain support
   * @param name Cookie name
   * @param value Cookie value
   * @param days Expiry in days (default 365)
   */
  set(name: string, value: string, days: number = 365): void {
    const date = new Date();
    date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
    const expires = `expires=${date.toUTCString()}`;

    // Determine if we're in production (not localhost)
    const isLocal = typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

    // Use configured domain in production, no domain in localhost
    const domainPart = isLocal ? '' : `; domain=${COOKIE_DOMAIN}`;
    const securePart = isLocal ? '' : '; secure';

    // URL encode the value (important for JWT tokens with special characters)
    const encodedValue = encodeURIComponent(value);
    const cookieString = `${name}=${encodedValue}; ${expires}; path=/${domainPart}${securePart}; samesite=lax`;
    document.cookie = cookieString;

    console.log(`🍪 Set cookie: ${name} (domain: ${isLocal ? 'localhost' : COOKIE_DOMAIN})`);
  },

  /**
   * Set a cookie with max-age (in seconds) instead of expiry date
   * @param name Cookie name
   * @param value Cookie value
   * @param maxAge Max age in seconds
   */
  setWithMaxAge(name: string, value: string, maxAge: number): void {
    const isLocal = typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

    const domainPart = isLocal ? '' : `; domain=${COOKIE_DOMAIN}`;
    const securePart = isLocal ? '' : '; secure';

    const cookieString = `${name}=${value}; path=/; max-age=${maxAge}${domainPart}${securePart}; samesite=lax`;
    document.cookie = cookieString;

    console.log(`🍪 Set cookie with max-age: ${name} (domain: ${isLocal ? 'localhost' : COOKIE_DOMAIN})`);
  },

  /**
   * Get a cookie value
   */
  get(name: string): string | null {
    if (typeof document === 'undefined') return null;

    const nameEQ = `${name}=`;
    const cookies = document.cookie.split(';');

    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.indexOf(nameEQ) === 0) {
        // URL decode the value when retrieving
        const encodedValue = cookie.substring(nameEQ.length);
        return decodeURIComponent(encodedValue);
      }
    }

    return null;
  },

  /**
   * Remove a cookie
   */
  remove(name: string): void {
    const isLocal = typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

    const domainPart = isLocal ? '' : `; domain=${COOKIE_DOMAIN}`;

    // Set expiry to past date
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/${domainPart}`;

    console.log(`🍪 Removed cookie: ${name}`);
  },

  /**
   * Check if a cookie exists
   */
  has(name: string): boolean {
    return this.get(name) !== null;
  }
};
