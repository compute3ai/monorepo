/**
 * DateTime utilities for consistent timezone-aware formatting across the app
 * Automatically uses the user's browser timezone
 */

/**
 * Format a date string in the user's local timezone
 * - If today: "14:30" (just time)
 * - If this year: "Nov 15 14:30"
 * - If older: "Nov 15, 2024 14:30"
 */
export const formatDateTime = (dateString: string | number | null | undefined): string => {
  if (!dateString) return 'Never';

  let date: Date;

  // Handle Unix timestamps (seconds since epoch, with optional microseconds)
  if (typeof dateString === 'number' || /^\d+(\.\d+)?$/.test(String(dateString))) {
    const timestamp = typeof dateString === 'number' ? dateString : parseFloat(String(dateString));
    // Unix timestamps are in seconds, JavaScript expects milliseconds
    date = new Date(timestamp * 1000);
  } else {
    date = new Date(dateString);
  }

  // Check if date is valid
  if (isNaN(date.getTime())) return 'Invalid date';

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const isThisYear = date.getFullYear() === now.getFullYear();

  if (isToday) {
    // Just show time for today
    return date.toLocaleString(undefined, {
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  if (isThisYear) {
    // Show month, day, and time for this year
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  // Show full date for older dates
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

/**
 * Format a date string in the user's local timezone without seconds
 * Example: "Jan 15, 2025, 02:30 PM"
 */
export const formatDateTimeShort = (dateString: string | number | null | undefined): string => {
  if (!dateString) return 'Never';

  let date: Date;

  // Handle Unix timestamps (seconds since epoch, with optional microseconds)
  if (typeof dateString === 'number' || /^\d+(\.\d+)?$/.test(String(dateString))) {
    const timestamp = typeof dateString === 'number' ? dateString : parseFloat(String(dateString));
    date = new Date(timestamp * 1000);
  } else {
    date = new Date(dateString);
  }

  if (isNaN(date.getTime())) return 'Invalid date';

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

/**
 * Format just the date in the user's local timezone
 * Example: "Jan 15, 2025"
 */
export const formatDate = (dateString: string | number | null | undefined): string => {
  if (!dateString) return 'Never';

  let date: Date;

  // Handle Unix timestamps (seconds since epoch, with optional microseconds)
  if (typeof dateString === 'number' || /^\d+(\.\d+)?$/.test(String(dateString))) {
    const timestamp = typeof dateString === 'number' ? dateString : parseFloat(String(dateString));
    date = new Date(timestamp * 1000);
  } else {
    date = new Date(dateString);
  }

  if (isNaN(date.getTime())) return 'Invalid date';

  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
};

/**
 * Format a relative time (e.g., "2 hours ago", "3 days ago")
 */
export const formatRelativeTime = (dateString: string | number | null | undefined): string => {
  if (!dateString) return 'Never';

  let date: Date;

  // Handle Unix timestamps (seconds since epoch, with optional microseconds)
  if (typeof dateString === 'number' || /^\d+(\.\d+)?$/.test(String(dateString))) {
    const timestamp = typeof dateString === 'number' ? dateString : parseFloat(String(dateString));
    date = new Date(timestamp * 1000);
  } else {
    date = new Date(dateString);
  }

  if (isNaN(date.getTime())) return 'Invalid date';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'Just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;
  if (diffDays < 30) return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;

  // For older dates, show the actual date
  return formatDate(dateString);
};

/**
 * Get the user's timezone name
 * Example: "America/Los_Angeles"
 */
export const getUserTimezone = (): string => {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
};

/**
 * Get the user's timezone abbreviation
 * Example: "PST" or "UTC"
 */
export const getTimezoneAbbr = (): string => {
  const date = new Date();
  const formatted = date.toLocaleString(undefined, { timeZoneName: 'short' });
  const parts = formatted.split(' ');
  return parts[parts.length - 1];
};
