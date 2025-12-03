/**
 * Transaction utility functions
 */

// Transaction types from backend
export const TRANSACTION_TYPES = {
  TOP_UP: "top_up",
  JOB: "job",
  GENERATION: "generation",
  LLM: "llm",
  REFUND: "refund",
  ADJUSTMENT: "adjustment",
  SUBSCRIPTION: "subscription",
  EXPIRY: "expiry",
} as const;

// Transaction statuses
export const TRANSACTION_STATUSES = {
  PENDING: "pending",
  COMPLETED: "completed",
  FAILED: "failed",
} as const;

/**
 * Format transaction type for display
 * @param type - Transaction type from backend (e.g., "top_up")
 * @returns Formatted display name (e.g., "Top Up")
 */
export function formatTransactionType(type: string): string {
  const typeMap: Record<string, string> = {
    top_up: "Top Up",
    job: "Job",
    generation: "Generation",
    llm: "LLM",
    refund: "Refund",
    adjustment: "Adjustment",
    subscription: "Subscription",
    expiry: "Expiry",
  };

  return typeMap[type] || type;
}

/**
 * Get badge color classes for transaction type
 * @param type - Transaction type from backend
 * @returns Tailwind CSS classes for badge styling
 */
export function getTransactionTypeBadgeClass(type: string): string {
  const classMap: Record<string, string> = {
    top_up: "bg-blue-100 text-blue-800 border-blue-200",
    job: "bg-purple-100 text-purple-800 border-purple-200",
    generation: "bg-pink-100 text-pink-800 border-pink-200",
    llm: "bg-indigo-100 text-indigo-800 border-indigo-200",
    refund: "bg-green-100 text-green-800 border-green-200",
    adjustment: "bg-yellow-100 text-yellow-800 border-yellow-200",
    subscription: "bg-orange-100 text-orange-800 border-orange-200",
    expiry: "bg-gray-100 text-gray-800 border-gray-200",
  };

  return classMap[type] || "bg-gray-100 text-gray-800 border-gray-200";
}

/**
 * Get badge color classes for transaction status
 * @param status - Transaction status from backend
 * @returns Tailwind CSS classes for badge styling
 */
export function getTransactionStatusBadgeClass(status: string): string {
  const classMap: Record<string, string> = {
    completed: "bg-green-50 text-green-700 border-green-200",
    pending: "bg-yellow-50 text-yellow-700 border-yellow-200",
    failed: "bg-red-50 text-red-700 border-red-200",
  };

  return classMap[status] || "bg-gray-50 text-gray-700 border-gray-200";
}

/**
 * Capitalize transaction status for display
 * @param status - Transaction status from backend
 * @returns Capitalized status
 */
export function formatTransactionStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
