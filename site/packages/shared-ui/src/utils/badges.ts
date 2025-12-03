/**
 * Common badge styling utilities for consistent status/state display
 */

/**
 * Get badge class based on status/state
 * Works for both job states and transaction statuses
 */
export const getBadgeClass = (status: string): string => {
  const normalizedStatus = status.toLowerCase();

  switch (normalizedStatus) {
    // Success states
    case 'succeeded':
    case 'completed':
      return 'bg-green-100 text-green-800 border-green-200';

    // Warning/pending states
    case 'pending':
    case 'queued':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200';

    // Info/in-progress states
    case 'assigned':
    case 'running':
      return 'bg-blue-100 text-blue-800 border-blue-200';

    // Error/failure states
    case 'failed':
    case 'canceled':
      return 'bg-red-100 text-red-800 border-red-200';

    // Terminated/stopped states
    case 'terminated':
      return 'bg-gray-100 text-gray-800 border-gray-200';

    // Default
    default:
      return 'bg-gray-100 text-gray-800 border-gray-200';
  }
};
