/**
 * Currency conversion utilities for payment processing
 */

/**
 * Convert USD amount to Stripe cents
 * @param usdAmount Dollar amount (e.g., 10.50)
 * @returns Amount in cents (e.g., 1050)
 */
export function toStripeCents(usdAmount: number): number {
  return Math.floor(usdAmount * 100)
}

/**
 * Convert USD amount to USDC units (6 decimals) for x402
 * @param usdAmount Dollar amount (e.g., 0.10)
 * @returns Amount in USDC units (e.g., 100000)
 */
export function toUsdcUnits(usdAmount: number): number {
  return Math.floor(usdAmount * 1_000_000)
}

/**
 * Convert Stripe cents to USD amount
 * @param cents Amount in cents (e.g., 1050)
 * @returns Dollar amount (e.g., 10.50)
 */
export function fromStripeCents(cents: number): number {
  return cents / 100
}

/**
 * Convert USDC units (6 decimals) to USD amount
 * @param units Amount in USDC units (e.g., 100000)
 * @returns Dollar amount (e.g., 0.10)
 */
export function fromUsdcUnits(units: number): number {
  return units / 1_000_000
}
