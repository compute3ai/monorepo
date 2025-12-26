"use client";

import React, { useEffect, useState } from "react";
import { Header, Footer, useAuth, formatDateTime, getBadgeClass, AlertDialog, getRegionName, getRegionFlag } from "@compute3/shared-ui";
import { useRouter } from "next/navigation";
import AmountDisplay from "../../components/AmountDisplay";

interface Job {
  job_id: string;
  job_key: string;
  user_id: string;
  hostname: string | null;
  state: string;
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
  memory_gb: number | null;
  cpu_cores: number | null;
  runtime: number;
  assigned_to: string | null;
  created_at: string;
  launch_by: string;
  expires: string | null;
  assigned_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  completed: boolean | null;
}

type SortColumn = 'job_id' | 'gpu' | 'hostname' | 'state' | 'price_per_hour' | 'created_at';
type SortDirection = 'asc' | 'desc';

interface JobTransaction {
  id: string;
  amount_usd: string;
  status: string;
}

export default function JobsPage() {
  const { isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState<string>("all");
  const [sortColumn, setSortColumn] = useState<SortColumn>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [expandedJobTx, setExpandedJobTx] = useState<JobTransaction | null>(null);
  const [jobTransactions, setJobTransactions] = useState<Record<string, JobTransaction>>({});
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

  useEffect(() => {
    if (isAuthenticated) {
      fetchJobs();
    }
  }, [isAuthenticated, stateFilter]);

  // Auto-refresh jobs every 30 seconds (silent refresh)
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      fetchJobs(true);
    }, 30000);

    return () => clearInterval(interval);
  }, [isAuthenticated, stateFilter]);

  const fetchJobs = async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) {
        if (!silent) {
          setError('No auth token found');
          setLoading(false);
        }
        return;
      }

      const url = stateFilter === "all"
        ? `${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs`
        : `${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs?state=${stateFilter}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const jobsData = await response.json();
        // Handle both array (legacy) and paginated response
        setJobs(Array.isArray(jobsData) ? jobsData : jobsData.jobs || []);

        // Fetch transactions for all jobs
        const txResponse = await fetch(
          `${process.env.NEXT_PUBLIC_AUTH_BACKEND}/tx?page_size=100`,
          {
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json'
            }
          }
        );

        if (txResponse.ok) {
          const txData = await txResponse.json();
          // Create a map of job_id to transaction
          const txMap: Record<string, JobTransaction> = {};
          for (const tx of txData.transactions || []) {
            // Check both tx.job_id (new) and tx.meta?.job_id (legacy)
            const jobId = tx.job_id || tx.meta?.job_id;
            if (jobId && tx.transaction_type === 'job') {
              txMap[jobId] = {
                id: tx.id,
                amount_usd: tx.amount_usd,
                status: tx.status
              };
            }
          }
          setJobTransactions(txMap);
        }
      } else if (response.status === 404) {
        setJobs([]);
      } else if (!silent) {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to load jobs');
      }
    } catch (error) {
      console.error('Error fetching jobs:', error);
      if (!silent) {
        setError(error instanceof Error ? error.message : 'Unknown error');
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  const handleCancelJob = async (jobId: string, jobState: string) => {
    // Different messages based on whether job has started (will be billed)
    const isRunning = jobState === 'running';
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
          const authToken = document.cookie
            .split('; ')
            .find(row => row.startsWith('auth_token='))
            ?.split('=')[1];

          if (!authToken) return;

          const response = await fetch(`${process.env.NEXT_PUBLIC_AUTH_BACKEND}/jobs/${jobId}`, {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${authToken}`,
              'Content-Type': 'application/json'
            }
          });

          if (response.ok) {
            fetchJobs();
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

  const handleCloneJob = (job: Job) => {
    // Store job config in sessionStorage for the launch page to read
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
      auth: (job as any).auth  // Auth field from backend
    };
    sessionStorage.setItem('cloneJobConfig', JSON.stringify(cloneConfig));
    router.push('/job');
  };

  const formatJobState = (state: string): string => {
    // Normalize legacy "completed" to "succeeded" for display
    if (state === 'completed') {
      return 'succeeded';
    }
    return state;
  };

  const formatSecondsHumanReadable = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0 && minutes > 0) {
      return `${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h`;
    } else if (minutes > 0) {
      return `${minutes}m`;
    } else {
      return `${secs}s`;
    }
  };

  const getJobDuration = (job: Job): number | null => {
    if (!job.started_at || !job.completed_at) return null;
    const startedTime = typeof job.started_at === 'number'
      ? job.started_at
      : new Date(job.started_at).getTime() / 1000;
    const completedTime = typeof job.completed_at === 'number'
      ? job.completed_at
      : new Date(job.completed_at).getTime() / 1000;
    return Math.max(0, Math.floor(completedTime - startedTime));
  };

  const handleJobExpand = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      setExpandedJobTx(null);
      return;
    }

    setExpandedJobId(jobId);
    setExpandedJobTx(null);

    // Fetch transaction for this job
    try {
      const authToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('auth_token='))
        ?.split('=')[1];

      if (!authToken) return;

      // Fetch transactions and find the one for this job
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_AUTH_BACKEND}/tx?job_id=${jobId}`,
        {
          headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        // Get the first transaction for this job (should be the reservation)
        if (data.transactions && data.transactions.length > 0) {
          const tx = data.transactions[0];
          setExpandedJobTx({
            id: tx.id,
            amount_usd: tx.amount_usd,
            status: tx.status
          });
        }
      }
    } catch (error) {
      console.error('Error fetching job transaction:', error);
    }
  };

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      // Toggle direction if clicking the same column
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new column and default to ascending (except created_at defaults to desc)
      setSortColumn(column);
      setSortDirection(column === 'created_at' ? 'desc' : 'asc');
    }
  };

  const sortedJobs = [...jobs].sort((a, b) => {
    let aValue: any;
    let bValue: any;

    switch (sortColumn) {
      case 'job_id':
        aValue = a.job_id;
        bValue = b.job_id;
        break;
      case 'gpu':
        aValue = `${a.gpu_count}x${a.gpu_type}`;
        bValue = `${b.gpu_count}x${b.gpu_type}`;
        break;
      case 'hostname':
        aValue = a.hostname || '';
        bValue = b.hostname || '';
        break;
      case 'state':
        aValue = a.state;
        bValue = b.state;
        break;
      case 'price_per_hour':
        aValue = a.price_per_hour;
        bValue = b.price_per_hour;
        break;
      case 'created_at':
        aValue = new Date(a.created_at).getTime();
        bValue = new Date(b.created_at).getTime();
        break;
      default:
        return 0;
    }

    if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
    return 0;
  });

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-900 text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <Header />

      <main className="flex-1 pt-20 relative">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="flex justify-between items-center mb-4">
            <h1 className="text-4xl font-bold text-gray-900">Jobs</h1>
            <button
              onClick={() => router.push('/job')}
              className="btn-primary text-white font-semibold py-2 px-6 rounded-lg"
            >
              Launch GPU
            </button>
          </div>

          {/* State Filter */}
          <div className="flex gap-2 mb-8">
            {['all', 'queued', 'running', 'succeeded', 'terminated', 'failed'].map((state) => (
              <button
                key={state}
                onClick={() => setStateFilter(state)}
                className={`px-4 py-2 rounded-lg font-semibold text-sm ${
                  stateFilter === state
                    ? 'btn-primary text-white'
                    : 'btn-secondary'
                }`}
              >
                {state.charAt(0).toUpperCase() + state.slice(1)}
              </button>
            ))}
          </div>

          {loading && <div className="text-gray-600">Loading jobs...</div>}
          {error && <div className="text-red-600 mb-4">Error: {error}</div>}

          {!loading && !error && jobs.length === 0 && (
            <div className="bg-white p-8 rounded-lg shadow text-center">
              <p className="text-gray-600 mb-4">You don't have any jobs yet.</p>
            </div>
          )}

          {!loading && jobs.length > 0 && (
            <div className="bg-white rounded-lg shadow overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-24"
                      onClick={() => handleSort('state')}
                    >
                      <div className="flex items-center gap-1">
                        Status
                        {sortColumn === 'state' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-32"
                      onClick={() => handleSort('job_id')}
                    >
                      <div className="flex items-center gap-1">
                        Job ID
                        {sortColumn === 'job_id' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-28"
                      onClick={() => handleSort('gpu')}
                    >
                      <div className="flex items-center gap-1">
                        Type
                        {sortColumn === 'gpu' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider w-24">
                      Region
                    </th>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-64"
                      onClick={() => handleSort('hostname')}
                    >
                      <div className="flex items-center gap-1">
                        Hostname
                        {sortColumn === 'hostname' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                      onClick={() => handleSort('price_per_hour')}
                    >
                      <div className="flex items-center gap-1">
                        Price/Hour
                        {sortColumn === 'price_per_hour' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider w-20">
                      Cost
                    </th>
                    <th
                      className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider cursor-pointer hover:bg-gray-100 w-20"
                      onClick={() => handleSort('created_at')}
                    >
                      <div className="flex items-center gap-1">
                        Created
                        {sortColumn === 'created_at' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sortedJobs.map((job) => (
                    <React.Fragment key={job.job_id}>
                    <tr
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={(e) => {
                        // Ctrl/Cmd+click opens in new tab
                        if (e.ctrlKey || e.metaKey) {
                          window.open(`/job/${job.job_id}`, '_blank');
                        } else {
                          handleJobExpand(job.job_id);
                        }
                      }}
                    >
                      <td className="px-6 py-4 whitespace-nowrap w-24">
                        <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${getBadgeClass(job.state)}`}>
                          {formatJobState(job.state)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap w-32">
                        <span className="font-mono text-sm text-gray-900">
                          {job.job_id.substring(0, 8)}...
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap w-28">
                        <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
                          {job.gpu_count}x {job.gpu_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap w-24 text-sm">
                        <span className="inline-flex items-center gap-1" title={getRegionName(job.region)}>
                          <span className="text-lg">{getRegionFlag(job.region)}</span>
                          <span className="text-gray-700">{job.region}</span>
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm font-mono w-64">
                        {job.hostname ? (
                          job.ports?.lb ? (
                            <a
                              href={`https://${job.hostname}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 hover:underline truncate"
                            >
                              <span className="truncate">{job.hostname}</span>
                              <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                            </a>
                          ) : (
                            <span className="text-gray-600 truncate block">{job.hostname}</span>
                          )
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        ${job.price_per_hour.toFixed(6)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm w-20">
                        {jobTransactions[job.job_id] ? (
                          <span className={
                            jobTransactions[job.job_id].status.toLowerCase() === 'pending'
                              ? 'text-gray-500 italic'
                              : job.state === 'failed' || job.state === 'canceled'
                              ? 'line-through text-gray-400'
                              : ''
                          }>
                            <AmountDisplay amountUsd={jobTransactions[job.job_id].amount_usd} />
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 w-20">
                        {formatDateTime(job.created_at)}
                      </td>
                    </tr>
                    {/* Expandable Details Row */}
                    {expandedJobId === job.job_id && (
                      <tr>
                        <td colSpan={8} className="px-6 py-4 bg-white">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                                Job ID
                              </h3>
                              <p className="font-mono text-sm text-gray-900">{job.job_id}</p>
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

                            <div>
                              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                                {(job.state === 'queued' || job.state === 'assigned') ? 'Reserved Amount' : 'Total Cost'}
                              </h3>
                              {expandedJobTx ? (
                                <p className={
                                  job.state === 'queued' || job.state === 'assigned'
                                    ? 'text-gray-500 italic'
                                    : job.state === 'failed' || job.state === 'canceled'
                                    ? 'line-through text-gray-400'
                                    : ''
                                }>
                                  <AmountDisplay amountUsd={expandedJobTx.amount_usd} />
                                  {(job.state === 'queued' || job.state === 'assigned') && (
                                    <span className="text-xs ml-1">(pending)</span>
                                  )}
                                </p>
                              ) : (
                                <p className="text-gray-400 text-sm">Loading...</p>
                              )}
                            </div>

                            {job.hostname && (
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
                                      onClick={(e) => e.stopPropagation()}
                                      className="font-mono text-sm text-blue-600 hover:text-blue-700 hover:underline"
                                    >
                                      {job.hostname}
                                    </a>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        window.open(`https://${job.hostname}`, '_blank');
                                      }}
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
                            )}

                            {job.assigned_to && (
                              <div>
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

                            {getJobDuration(job) !== null && (
                              <div>
                                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                                  Duration
                                </h3>
                                <p className="text-gray-900">{formatSecondsHumanReadable(getJobDuration(job)!)}</p>
                              </div>
                            )}

                            <div>
                              <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                                Docker Image
                              </h3>
                              <p className="font-mono text-sm text-gray-900 truncate" title={job.docker_image}>{job.docker_image}</p>
                            </div>
                          </div>
                          <div className="flex gap-3 mt-4 pt-4 border-t border-gray-200">
                            <a
                              href={`/job/${job.job_id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="btn-primary text-white font-semibold py-2 px-4 rounded-lg"
                            >
                              View Job
                            </a>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCloneJob(job);
                              }}
                              className="btn-secondary font-semibold py-2 px-4 rounded-lg"
                            >
                              Clone Job
                            </button>
                            {(job.state === 'queued' || job.state === 'assigned' || job.state === 'running') && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCancelJob(job.job_id, job.state);
                                }}
                                className="btn-secondary text-red-600 font-semibold py-2 px-4 rounded-lg hover:bg-red-50"
                              >
                                Cancel Job
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      <Footer />

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
