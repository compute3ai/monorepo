"use client";

import React, { useEffect, useState, useRef } from "react";
import { Header, Footer, useAuth, formatDateTime, getBadgeClass, cookieUtils, AlertDialog, Modal, getRegionName, getRegionFlag } from "@compute3/shared-ui";
import { useRouter, useParams } from "next/navigation";

interface Job {
  job_id: string;
  job_key: string;
  state: string;
  hostname: string | null;
  gpu_type: string;
  gpu_count: number;
  region: string;
  interruptible: boolean;
  price_per_hour: number;
  price_per_second: number;
  docker_image: string;
  dockerfile: string | null;
  hf_space: string | null;
  command: string[];
  env_vars: { [key: string]: string } | null;
  ports: { [key: string]: number } | null;
  auth: boolean;
  runtime: number;  // Runtime in seconds (expiration = started_at + runtime)
  memory_gb: number | null;
  cpu_cores: number | null;
  created_at: string | number;  // Unix timestamp (seconds) or ISO string
  assigned_at: string | number | null;
  started_at: string | number | null;
  completed_at: string | number | null;
  assigned_to: string | null;
}

interface InstanceConfig {
  gpu_count: number;
  cpu_cores: number;
  memory_gb: number;
  storage_gb: number;
  regions: string[];
}

interface InstanceType {
  name: string;
  description: string;
  configs: InstanceConfig[];
}

export default function JobDetailPage() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const params = useParams();
  const jobId = params?.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [logs, setLogs] = useState<string>("");
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [jobLoading, setJobLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [showExtendModal, setShowExtendModal] = useState(false);
  const [extensionSeconds, setExtensionSeconds] = useState(3600);
  const [extending, setExtending] = useState(false);
  const [metrics, setMetrics] = useState<any>(null);
  const [instanceTypes, setInstanceTypes] = useState<Record<string, InstanceType>>({});

  const wsRef = useRef<WebSocket | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const metricsIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const hasConnectedToWSRef = useRef<boolean>(false);
  const hasFetchedLogsRef = useRef<boolean>(false);
  const hasFetchedTokenRef = useRef<boolean>(false);
  const logBufferRef = useRef<string[]>([]);
  const logFlushIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [alertDialog, setAlertDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    type: "info" | "warning" | "error" | "success";
    onConfirm?: () => void | Promise<void>;
    showCancel?: boolean;
  }>({
    isOpen: false,
    title: "",
    message: "",
    type: "info",
  });

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isLoading, isAuthenticated, router]);

  // Fetch job details on mount
  useEffect(() => {
    if (isAuthenticated && jobId) {
      fetchJob();
    }
  }, [isAuthenticated, jobId]);

  // Fetch instance types for cpu_cores fallback
  useEffect(() => {
    const fetchInstanceTypes = async () => {
      try {
        const instancesUrl = process.env.NEXT_PUBLIC_INSTANCES_API_URL;
        if (!instancesUrl) return;
        const response = await fetch(`${instancesUrl}/types`);
        if (response.ok) {
          const data = await response.json();
          setInstanceTypes(data);
        }
      } catch (err) {
        console.error('Failed to fetch instance types:', err);
      }
    };
    fetchInstanceTypes();
  }, []);

  // Get effective cpu_cores from job or instance types lookup
  const effectiveCpuCores = React.useMemo(() => {
    if (job?.cpu_cores) return job.cpu_cores;
    if (!job || !instanceTypes[job.gpu_type.toLowerCase()]) return null;
    const typeInfo = instanceTypes[job.gpu_type.toLowerCase()];
    const config = typeInfo.configs.find(c => c.gpu_count === job.gpu_count);
    return config?.cpu_cores || null;
  }, [job, instanceTypes]);

  // State machine: handle behavior based on job state
  useEffect(() => {
    if (!job) return;

    const state = job.state;

    // Only poll for queued/assigned states (waiting for job to start)
    if (['queued', 'assigned'].includes(state)) {
      startPolling();
    } else {
      stopPolling();
    }

    // Fetch job token when hostname is available (assigned or running state)
    if (job.hostname && !hasFetchedTokenRef.current) {
      hasFetchedTokenRef.current = true;
      fetchJobToken(job.hostname);
    }

    // Handle state-specific behavior
    if (state === 'assigned' && !hasConnectedToWSRef.current) {
      // Try to connect to websocket
      hasConnectedToWSRef.current = true;
      connectWebSocket(job.job_key);
    } else if (state === 'running') {
      // Fetch logs then connect to websocket
      if (!hasFetchedLogsRef.current) {
        hasFetchedLogsRef.current = true;
        fetchLogs(job.job_key).then(() => {
          if (!hasConnectedToWSRef.current) {
            hasConnectedToWSRef.current = true;
            connectWebSocket(job.job_key);
          }
        });
      }
    } else if (['succeeded', 'terminated', 'failed'].includes(state)) {
      // Just fetch logs
      if (!hasFetchedLogsRef.current) {
        hasFetchedLogsRef.current = true;
        fetchLogs(job.job_key);
      }
    }

    return () => {
      stopPolling();
    };
  }, [job?.state, job?.job_key, job?.hostname]);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (logFlushIntervalRef.current) {
        clearInterval(logFlushIntervalRef.current);
      }
      stopPolling();
    };
  }, []);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, liveLogs]);

  // Countdown timer for job expiration (calculated from started_at + runtime)
  useEffect(() => {
    if (!job || !job.started_at) {
      setTimeRemaining(null);
      return;
    }

    // Only show countdown for active jobs
    if (!['queued', 'assigned', 'running'].includes(job.state)) {
      setTimeRemaining(null);
      return;
    }

    const updateCountdown = () => {
      const now = Date.now();
      // Backend returns Unix timestamp in seconds, convert to milliseconds
      const startedTime = typeof job.started_at === 'number'
        ? job.started_at * 1000
        : new Date(job.started_at!).getTime();
      const expiresTime = startedTime + (job.runtime * 1000);
      const remaining = Math.max(0, Math.floor((expiresTime - now) / 1000));
      setTimeRemaining(remaining);
    };

    // Update immediately
    updateCountdown();

    // Update every second
    const interval = setInterval(updateCountdown, 1000);

    return () => clearInterval(interval);
  }, [job?.started_at, job?.runtime, job?.state]);

  const formatTimeRemaining = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const getAuthToken = () => {
    return document.cookie
      .split('; ')
      .find(row => row.startsWith('auth_token='))
      ?.split('=')[1];
  };

  const fetchJob = async () => {
    setJobLoading(true);
    setError(null);

    try {
      const authToken = getAuthToken();
      if (!authToken) {
        setError('No auth token found');
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 404) {
          setError('Job not found');
        } else {
          setError('Failed to fetch job details');
        }
        return;
      }

      const jobData = await response.json();
      setJob(jobData);
    } catch (err) {
      console.error('Error fetching job:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setJobLoading(false);
    }
  };

  const fetchJobToken = async (hostname: string) => {
    try {
      const authToken = getAuthToken();
      if (!authToken) {
        console.error('No auth token found for job token fetch');
        return;
      }

      console.log('🔑 Fetching job token for cross-domain auth...');

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}/token`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.job_jwt && data.hostname) {
          // JWT tokens typically expire in 48 hours (2 days)
          const daysUntilExpiry = 2;

          // Extract subdomain from hostname (e.g., "fluffy-cat" from "fluffy-cat.compute3.ai")
          const subdomain = data.hostname.split('.')[0];
          const cookieName = `${subdomain}-token`;
          cookieUtils.set(cookieName, data.job_jwt, daysUntilExpiry);

          console.log(`✅ Job token set as ${cookieName} (expires in ${daysUntilExpiry} days)`);
        }
      } else if (response.status === 400) {
        // Job not assigned yet or auth not enabled - this is expected
        console.log('⏳ Job token not available yet (job not assigned or auth disabled)');
      } else {
        console.error('Failed to fetch job token:', response.status);
      }
    } catch (err) {
      console.error('Error fetching job token:', err);
    }
  };

  const fetchLogs = async (jobKey: string): Promise<void> => {
    try {
      const authToken = getAuthToken();
      if (!authToken) {
        console.error('No auth token found');
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}/logs`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        const fetchedLogs = data.logs || '';
        if (fetchedLogs) {
          setLogs(fetchedLogs);
        }
      } else if (response.status !== 404) {
        console.error('Failed to fetch logs:', response.status);
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  const startPolling = () => {
    if (pollingIntervalRef.current) return;

    const poll = async () => {
      try {
        const authToken = getAuthToken();
        if (!authToken) return;

        const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}`, {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const jobData = await response.json();
          setJob(jobData);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    pollingIntervalRef.current = setInterval(poll, 5000);
    poll(); // Initial poll
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const flushLogBuffer = () => {
    if (logBufferRef.current.length > 0) {
      const newLogs = logBufferRef.current;
      logBufferRef.current = [];
      setLiveLogs(prev => [...prev, ...newLogs]);
    }
  };

  const connectWebSocket = (jobKey: string) => {
    if (wsRef.current) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || '';
    const fullWsUrl = `${wsUrl}/logs/${jobKey}`;

    setWsStatus('connecting');

    try {
      const ws = new WebSocket(fullWsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
        // Start flushing log buffer every 100ms
        if (!logFlushIntervalRef.current) {
          logFlushIntervalRef.current = setInterval(flushLogBuffer, 100);
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'log' && data.log) {
            // Buffer logs instead of updating state immediately
            logBufferRef.current.push(data.log.trimEnd());
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsStatus('disconnected');
      };

      ws.onclose = () => {
        setWsStatus('disconnected');
        wsRef.current = null;
        // Flush any remaining logs and stop the interval
        flushLogBuffer();
        if (logFlushIntervalRef.current) {
          clearInterval(logFlushIntervalRef.current);
          logFlushIntervalRef.current = null;
        }
      };
    } catch (err) {
      console.error('Failed to connect WebSocket:', err);
      setWsStatus('disconnected');
    }
  };

  const handleCancelJob = async () => {
    const isRunning = job?.state === 'running';
    const message = isRunning
      ? 'This job is running and you will be charged for the time already used. Cancel anyway?'
      : 'Are you sure you want to cancel this job?';

    setAlertDialog({
      isOpen: true,
      title: "Cancel Job",
      message,
      type: "warning",
      showCancel: true,
      onConfirm: async () => {
        try {
          const authToken = getAuthToken();
          if (!authToken) {
            setAlertDialog({
              isOpen: true,
              title: "Error",
              message: 'No auth token found',
              type: "error",
            });
            return;
          }

          const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json'
            }
          });

          if (response.ok) {
            fetchJob();
          } else {
            const error = await response.json();
            setAlertDialog({
              isOpen: true,
              title: "Error",
              message: error.detail || 'Failed to cancel job',
              type: "error",
            });
          }
        } catch (error) {
          console.error('Error canceling job:', error);
          setAlertDialog({
            isOpen: true,
            title: "Error",
            message: 'Failed to cancel job',
            type: "error",
          });
        }
      }
    });
  };

  const handleCloneJob = () => {
    if (!job) return;

    const cloneConfig = {
      gpu_type: job.gpu_type,
      gpu_count: job.gpu_count,
      region: job.region,
      interruptible: job.interruptible,
      docker_image: job.docker_image,
      dockerfile: job.dockerfile,
      hf_space: job.hf_space,
      command: job.command,
      runtime: job.runtime,
      env_vars: job.env_vars,
      ports: job.ports,
      auth: job.auth
    };
    sessionStorage.setItem('cloneJobConfig', JSON.stringify(cloneConfig));
    router.push('/job');
  };

  const formatSecondsHumanReadable = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours > 0 && minutes > 0) {
      return `${hours} hour${hours > 1 ? 's' : ''} ${minutes} minute${minutes > 1 ? 's' : ''}`;
    } else if (hours > 0) {
      return `${hours} hour${hours > 1 ? 's' : ''}`;
    } else if (minutes > 0) {
      return `${minutes} minute${minutes > 1 ? 's' : ''}`;
    } else {
      return `${seconds} second${seconds !== 1 ? 's' : ''}`;
    }
  };

  const getPowerColor = (watts: number): string => {
    if (watts < 40) return 'text-blue-600';
    if (watts < 80) return 'text-green-600';
    if (watts < 200) return 'text-yellow-600';
    if (watts < 400) return 'text-orange-600';
    return 'text-red-600';
  };

  const fetchMetrics = async () => {
    try {
      const authToken = getAuthToken();
      if (!authToken) return;

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}/metrics`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      } else if (response.status === 400 || response.status === 503 || response.status === 504) {
        // Job not running or metrics not available - stop polling
        stopMetricsPolling();
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  const startMetricsPolling = () => {
    // Clear any existing interval
    if (metricsIntervalRef.current) {
      clearInterval(metricsIntervalRef.current);
    }

    // Fetch immediately
    fetchMetrics();

    // Poll every 5 seconds
    metricsIntervalRef.current = setInterval(fetchMetrics, 5000);
  };

  const stopMetricsPolling = () => {
    if (metricsIntervalRef.current) {
      clearInterval(metricsIntervalRef.current);
      metricsIntervalRef.current = null;
    }
    setMetrics(null);
  };

  // Start/stop metrics polling based on job state
  useEffect(() => {
    if (job && (job.state === 'running' || job.state === 'assigned')) {
      startMetricsPolling();
    } else {
      stopMetricsPolling();
    }

    return () => {
      stopMetricsPolling();
    };
  }, [job?.state, jobId]);

  const handleExtendJob = async () => {
    if (!job) return;

    try {
      const authToken = getAuthToken();
      if (!authToken) {
        setAlertDialog({
          isOpen: true,
          title: "Error",
          message: 'No auth token found',
          type: "error",
        });
        return;
      }

      setExtending(true);

      // Calculate new total runtime
      const new_runtime = job.runtime + extensionSeconds;

      const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ runtime: new_runtime })
      });

      if (response.ok) {
        setShowExtendModal(false);
        setExtensionSeconds(3600);
        fetchJob(); // Refresh job data
        setAlertDialog({
          isOpen: true,
          title: "Success",
          message: `Job extended by ${formatSecondsHumanReadable(extensionSeconds)}`,
          type: "success",
        });
      } else {
        const error = await response.json();
        setAlertDialog({
          isOpen: true,
          title: "Error",
          message: error.detail || 'Failed to extend job',
          type: "error",
        });
      }
    } catch (error) {
      console.error('Error extending job:', error);
      setAlertDialog({
        isOpen: true,
        title: "Error",
        message: 'Failed to extend job',
        type: "error",
      });
    } finally {
      setExtending(false);
    }
  };

  // Determine if we should show the terminal
  const shouldShowTerminal = job && !['queued', 'canceled'].includes(job.state);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-900 text-xl">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col overflow-x-hidden">
        <Header />
        <main className="flex-1 pt-20 relative">
          <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
              <h2 className="text-xl font-bold mb-2">Error</h2>
              <p>{error}</p>
              <button
                onClick={() => router.push('/jobs')}
                className="mt-4 btn-secondary font-semibold py-2 px-4 rounded-lg"
              >
                Back to Jobs
              </button>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (jobLoading || !job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-900 text-xl">Loading job details...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <style jsx>{`
        .terminal-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .terminal-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .terminal-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.3);
          border-radius: 4px;
        }
        .terminal-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.5);
        }
      `}</style>
      <Header />

      <main className="flex-1 pt-20 relative">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-4xl font-bold text-gray-900">Job Details</h1>
            <div className="flex gap-3">
              <button
                onClick={handleCloneJob}
                className="btn-secondary font-semibold py-2 px-4 rounded-lg"
              >
                Clone Job
              </button>
              <button
                onClick={() => router.push('/jobs')}
                className="btn-secondary font-semibold py-2 px-4 rounded-lg"
              >
                Back to Jobs
              </button>
            </div>
          </div>

          {/* HTTPS Load Balancer Access Banner */}
          {job.hostname && job.ports?.lb && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-semibold text-blue-900">HTTPS Load Balancer Active</h3>
                      {job.auth ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 rounded-full border border-green-300">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                          </svg>
                          Cookie Required
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 rounded-full border border-yellow-300">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                          </svg>
                          Public Access
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-blue-700">Container port {job.ports.lb} is accessible via HTTPS</p>
                  </div>
                </div>
                <a
                  href={`https://${job.hostname}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold text-sm"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  Open Application
                </a>
              </div>
            </div>
          )}

          {/* Job Details Card */}
          <div className="bg-white p-6 rounded-lg shadow mb-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Job ID
                </h3>
                <p className="font-mono text-sm text-gray-900">{job.job_id}</p>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  State
                </h3>
                <span className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full border ${getBadgeClass(job.state)}`}>
                  {job.state}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  GPU Configuration
                </h3>
                <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
                  {job.gpu_count}x {job.gpu_type}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Price
                </h3>
                <p className="text-gray-900">${job.price_per_hour.toFixed(2)}/hour</p>
              </div>

              {job.hostname ? (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Hostname
                  </h3>
                  {job.ports?.lb ? (
                    <div className="flex items-center gap-2">
                      <a
                        href={`https://${job.hostname}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-sm text-blue-600 hover:text-blue-700 hover:underline"
                      >
                        {job.hostname}
                      </a>
                      <button
                        onClick={() => window.open(`https://${job.hostname}`, '_blank')}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                        title="Open in new tab"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                        Open
                      </button>
                    </div>
                  ) : (
                    <p className="font-mono text-sm text-gray-900">{job.hostname}</p>
                  )}
                </div>
              ) : (
                !job.started_at && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      Created At
                    </h3>
                    <p className="text-gray-900">{formatDateTime(job.created_at)}</p>
                  </div>
                )
              )}

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Region
                </h3>
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{getRegionFlag(job.region)}</span>
                  <span className="text-gray-900">{getRegionName(job.region)}</span>
                </div>
              </div>

              {job.runtime && !job.started_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Runtime Budget
                  </h3>
                  <p className="text-gray-900">{formatSecondsHumanReadable(job.runtime)}</p>
                </div>
              )}

              {job.runtime && job.price_per_hour && !job.started_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Estimated Cost
                  </h3>
                  <p className="text-gray-900">${(job.price_per_hour * job.runtime / 3600).toFixed(2)}</p>
                </div>
              )}

              {job.assigned_to && (
                <div className="md:col-span-2">
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Assigned To
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{job.assigned_to}</p>
                </div>
              )}

              {job.started_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Started At
                  </h3>
                  <p className="text-gray-900">{formatDateTime(job.started_at)}</p>
                </div>
              )}

              {timeRemaining !== null && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Time Remaining
                  </h3>
                  <div className="flex items-center gap-2">
                    <p className={`${timeRemaining < 300 ? 'text-red-600' : timeRemaining < 900 ? 'text-yellow-600' : 'text-green-600'}`}>
                      {formatTimeRemaining(timeRemaining)}
                    </p>
                    {timeRemaining < 300 && (
                      <svg className="w-4 h-4 text-red-600 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                    )}
                  </div>
                </div>
              )}

              {job.completed_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Completed At
                  </h3>
                  <p className="text-gray-900">{formatDateTime(job.completed_at)}</p>
                </div>
              )}

              {job.started_at && job.completed_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Duration
                  </h3>
                  <p className="text-gray-900">
                    {(() => {
                      const startedTime = typeof job.started_at === 'number'
                        ? job.started_at
                        : new Date(job.started_at!).getTime() / 1000;
                      const completedTime = typeof job.completed_at === 'number'
                        ? job.completed_at
                        : new Date(job.completed_at!).getTime() / 1000;
                      const durationSeconds = Math.max(0, Math.floor(completedTime - startedTime));
                      return formatSecondsHumanReadable(durationSeconds);
                    })()}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Live Metrics */}
          {metrics && (job.state === 'running' || job.state === 'assigned') && (
            <div className="bg-white rounded-lg shadow p-6 mb-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6">Live Metrics</h2>

              {/* System Metrics - Full Width */}
              {metrics.system && (
                <div className="mb-6 pb-6 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">
                    System
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* CPU Usage */}
                    {metrics.system.cpu_percent !== undefined && effectiveCpuCores && (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-600">CPU</span>
                          <span className="font-medium text-gray-900">
                            {(metrics.system.cpu_percent / effectiveCpuCores).toFixed(1)}%
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(metrics.system.cpu_percent / effectiveCpuCores, 100)}%` }}
                          ></div>
                        </div>
                      </div>
                    )}

                    {/* Memory Usage */}
                    {metrics.system.memory_used_mb !== undefined && metrics.system.memory_limit_mb !== undefined && (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-gray-600">RAM</span>
                          <span className="font-medium text-gray-900">
                            {(metrics.system.memory_used_mb / 1024).toFixed(1)} / {(metrics.system.memory_limit_mb / 1024).toFixed(1)} GB
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${(metrics.system.memory_used_mb / metrics.system.memory_limit_mb * 100).toFixed(1)}%` }}
                          ></div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* GPU Metrics - Grid */}
              {metrics.gpus && metrics.gpus.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">
                    GPUs
                  </h3>
                  <div className={`grid gap-6 ${
                    metrics.gpus.length === 1 ? 'grid-cols-1' :
                    metrics.gpus.length === 2 ? 'grid-cols-1 md:grid-cols-2' :
                    'grid-cols-1 md:grid-cols-2 lg:grid-cols-4'
                  }`}>
                    {metrics.gpus.map((gpu: any, idx: number) => (
                      <div key={idx} className="space-y-4">
                        <div className="flex items-center justify-between text-xs font-semibold text-gray-500 uppercase tracking-wider">
                          <span>GPU {idx}: {gpu.name}</span>
                          {gpu.power_draw_w !== undefined && (
                            <span className="text-gray-600 normal-case">
                              Power: <span className={getPowerColor(gpu.power_draw_w)}>{gpu.power_draw_w.toFixed(1)}W</span>
                            </span>
                          )}
                        </div>

                        <div className={metrics.gpus.length === 1 ? 'grid grid-cols-2 gap-6' : 'space-y-4'}>
                          {/* GPU Utilization */}
                          {gpu.utilization_gpu_percent !== undefined && (
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="text-gray-600">GPU</span>
                                <span className="font-medium text-gray-900">{gpu.utilization_gpu_percent}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                  style={{ width: `${gpu.utilization_gpu_percent}%` }}
                                ></div>
                              </div>
                            </div>
                          )}

                          {/* GPU Memory */}
                          {gpu.memory_used_mb !== undefined && gpu.memory_total_mb !== undefined && (
                            <div>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="text-gray-600">VRAM</span>
                                <span className="font-medium text-gray-900">
                                  {(gpu.memory_used_mb / 1024).toFixed(1)} / {(gpu.memory_total_mb / 1024).toFixed(1)} GB
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-green-600 h-2 rounded-full transition-all duration-300"
                                  style={{ width: `${(gpu.memory_used_mb / gpu.memory_total_mb * 100).toFixed(1)}%` }}
                                ></div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* State-specific content */}
          {job.state === 'queued' && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-yellow-800">
              <h2 className="text-lg font-semibold mb-2">Job has not launched yet</h2>
              <p>Waiting for an available instance to run this job...</p>
            </div>
          )}

          {job.state === 'canceled' && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-800">
              <h2 className="text-lg font-semibold mb-2">Job was canceled</h2>
              <p>This job was canceled and did not run.</p>
            </div>
          )}

          {/* Logs Terminal */}
          {shouldShowTerminal && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="bg-gray-800 px-4 py-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-gray-300 text-sm font-mono">Job Logs</span>
                  {job.state === 'assigned' && (
                    <span className="text-yellow-400 text-xs">
                      {wsStatus === 'connecting' ? '(connecting...)' : wsStatus === 'connected' ? '(connected)' : '(waiting...)'}
                    </span>
                  )}
                  {job.state === 'running' && wsStatus === 'connected' && (
                    <span className="text-green-400 text-xs">(live)</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
              </div>
              <div
                ref={terminalRef}
                className="terminal-scrollbar bg-black p-4 font-mono text-sm text-green-400 h-[600px] overflow-y-auto"
                style={{
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  scrollbarWidth: 'thin',
                  scrollbarColor: 'rgba(255, 255, 255, 0.3) transparent'
                }}
              >
                {!logs && liveLogs.length === 0 ? (
                  <div className="text-gray-500">
                    {job.state === 'assigned' ? 'Waiting for container to start...' : 'No logs available'}
                  </div>
                ) : (
                  <>
                    {logs && <div>{logs}</div>}
                    {liveLogs.map((log, idx) => (
                      <div key={`live-${idx}`}>{log}</div>
                    ))}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          {(job.state === 'queued' || job.state === 'assigned' || job.state === 'running') && (
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setShowExtendModal(true)}
                className="btn-primary text-white font-semibold py-2 px-6 rounded-lg"
              >
                Extend Runtime
              </button>
              <button
                onClick={handleCancelJob}
                className="btn-secondary text-red-600 font-semibold py-2 px-6 rounded-lg hover:bg-red-50"
              >
                Cancel Job
              </button>
            </div>
          )}
        </div>
      </main>

      <Footer />

      {/* Extend Job Modal */}
      <Modal
        isOpen={showExtendModal}
        onClose={() => setShowExtendModal(false)}
        title="Extend Job Runtime"
        maxWidth="md"
      >
        <div className="space-y-6">
          <div>
            <p className="text-sm text-gray-600 mb-4">
              Extend the runtime of this job. You will be charged for the additional time at ${job?.price_per_hour.toFixed(2)}/hour.
            </p>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Extension Duration (seconds)
            </label>
            <input
              type="number"
              min="1"
              max="604800"
              value={extensionSeconds}
              onChange={(e) => setExtensionSeconds(parseInt(e.target.value) || 1)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2"
              disabled={extending}
            />
            <p className="text-xs text-gray-600 mt-1">
              {formatSecondsHumanReadable(extensionSeconds)}
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Additional cost: ${((job?.price_per_second || 0) * extensionSeconds).toFixed(2)}
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleExtendJob}
              disabled={extending}
              className="flex-1 btn-primary text-white font-semibold py-2 px-4 rounded-lg disabled:opacity-50"
            >
              {extending ? 'Extending...' : 'Extend Job'}
            </button>
            <button
              onClick={() => setShowExtendModal(false)}
              disabled={extending}
              className="flex-1 btn-secondary font-semibold py-2 px-4 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      </Modal>

      <AlertDialog
        isOpen={alertDialog.isOpen}
        onClose={() => setAlertDialog({ ...alertDialog, isOpen: false })}
        title={alertDialog.title}
        message={alertDialog.message}
        type={alertDialog.type}
        onConfirm={alertDialog.onConfirm}
        showCancel={alertDialog.showCancel}
      />
    </div>
  );
}
