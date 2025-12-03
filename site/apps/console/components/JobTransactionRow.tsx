"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { formatDateTime, getBadgeClass } from "@compute3/shared-ui";
import AmountDisplay from "./AmountDisplay";

interface Transaction {
  id: string;
  user_id: string;
  amount: number;
  amount_usd: string;
  transaction_type: string;
  status: string;
  rewards: boolean;
  expires_at: string | null;
  job_id: string | null;
  meta: any;
  created_at: string;
  updated_at: string;
}

interface JobTransactionRowProps {
  tx: Transaction;
  isExpanded: boolean;
  onToggle: () => void;
}

export default function JobTransactionRow({ tx, isExpanded, onToggle }: JobTransactionRowProps) {
  const router = useRouter();
  const meta = tx.meta || {};

  const handleCloneJob = () => {
    if (!meta) return;

    const cloneConfig = {
      gpu_type: meta.gpu_type,
      gpu_count: meta.gpu_count,
      interruptible: meta.interruptible,
      docker_image: meta.docker_image,
      dockerfile: meta.dockerfile,
      hf_space: meta.hf_space,
      command: meta.command,
      runtime: meta.runtime_seconds,
      env_vars: meta.env_vars
    };
    sessionStorage.setItem('cloneJobConfig', JSON.stringify(cloneConfig));
    router.push('/job');
  };

  return (
    <React.Fragment>
      <tr
        onClick={onToggle}
        className="cursor-pointer hover:bg-gray-50 transition-colors"
      >
        <td className="px-6 py-4 whitespace-nowrap w-24">
          <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${getBadgeClass(tx.status)}`}>
            {tx.status.toLowerCase()}
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap w-32">
          <span className="font-mono text-sm text-gray-900">
            {tx.job_id ? tx.job_id.slice(0, 8) : tx.id.slice(0, 8)}...
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap w-28">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
              job
            </span>
            {tx.rewards && (
              <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-amber-100 text-amber-800 border-amber-200">
                rewards
              </span>
            )}
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          {meta.gpu_type ? (
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
              {meta.gpu_count || 1}x {meta.gpu_type}
            </span>
          ) : (
            <span className="text-sm text-gray-400">-</span>
          )}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
          <AmountDisplay amountUsd={tx.amount_usd} />
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
          {formatDateTime(tx.created_at)}
        </td>
        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
          <svg
            className={`w-5 h-5 text-gray-400 transform transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={7} className="px-6 py-4 bg-white">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {tx.job_id && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Job ID
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{tx.job_id}</p>
                </div>
              )}

              {meta.job_state && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Job State
                  </h3>
                  <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${getBadgeClass(meta.job_state)}`}>
                    {meta.job_state.toLowerCase()}
                  </span>
                </div>
              )}

              {meta.gpu_type && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    GPU Configuration
                  </h3>
                  <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
                    {meta.gpu_count || 1}x {meta.gpu_type}
                  </span>
                </div>
              )}

              {meta.price_per_hour !== undefined && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Price
                  </h3>
                  <p className="text-gray-900">${meta.price_per_hour.toFixed(2)}/hour</p>
                </div>
              )}

              {meta.runtime_seconds !== undefined && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Runtime
                  </h3>
                  <p className="text-gray-900">
                    {meta.runtime_seconds >= 3600
                      ? `${(meta.runtime_seconds / 3600).toFixed(2)} hours`
                      : meta.runtime_seconds >= 60
                      ? `${(meta.runtime_seconds / 60).toFixed(1)} minutes`
                      : `${meta.runtime_seconds} seconds`}
                  </p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {tx.status === 'pending' ? 'Reserved Amount' : 'Total Cost'}
                </h3>
                <p className={tx.status === 'pending' ? 'text-gray-500 italic' : ''}>
                  <AmountDisplay amountUsd={tx.amount_usd} className={tx.status === 'pending' ? 'text-gray-500' : ''} />
                  {tx.status === 'pending' && <span className="text-xs ml-1">(pending)</span>}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Created At
                </h3>
                <p className="text-gray-900">{formatDateTime(tx.created_at)}</p>
              </div>
            </div>
            {tx.job_id && (
              <div className="flex gap-3 mt-4 pt-4">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/job/${tx.job_id}`);
                  }}
                  className="btn-primary text-white font-semibold py-2 px-4 rounded-lg"
                >
                  View Job
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCloneJob();
                  }}
                  className="btn-secondary font-semibold py-2 px-4 rounded-lg"
                >
                  Clone Job
                </button>
              </div>
            )}
          </td>
        </tr>
      )}
    </React.Fragment>
  );
}
