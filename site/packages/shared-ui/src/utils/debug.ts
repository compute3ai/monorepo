// Debug logging helper - only logs in development
const DEBUG = process.env.NEXT_PUBLIC_AUTH_DEBUG === 'true'

export const debugLog = (...args: any[]) => {
  if (DEBUG) {
    console.log(...args)
  }
}
