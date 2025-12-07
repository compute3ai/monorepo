"use client";

import React from "react";
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

interface RenderTransactionRowProps {
  tx: Transaction;
  isExpanded: boolean;
  onToggle: () => void;
}

export default function RenderTransactionRow({ tx, isExpanded, onToggle }: RenderTransactionRowProps) {
  const meta = tx.meta || {};

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
            {meta.render_id ? meta.render_id.slice(0, 8) : tx.id.slice(0, 8)}...
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap w-28">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-purple-100 text-purple-800 border-purple-200">
              render
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
          ) : meta.render_type ? (
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
              {meta.render_type}
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
              {meta.render_id && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Render ID
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{meta.render_id}</p>
                </div>
              )}

              {meta.render_state && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Render State
                  </h3>
                  <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${getBadgeClass(meta.render_state)}`}>
                    {meta.render_state.toLowerCase()}
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

              {meta.render_type && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Render Type
                  </h3>
                  <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
                    {meta.render_type}
                  </span>
                </div>
              )}

              {meta.resolution && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Resolution
                  </h3>
                  <p className="text-gray-900">{meta.resolution}</p>
                </div>
              )}

              {meta.duration_seconds !== undefined && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Duration
                  </h3>
                  <p className="text-gray-900">
                    {meta.duration_seconds >= 3600
                      ? `${(meta.duration_seconds / 3600).toFixed(2)} hours`
                      : meta.duration_seconds >= 60
                      ? `${(meta.duration_seconds / 60).toFixed(1)} minutes`
                      : `${meta.duration_seconds} seconds`}
                  </p>
                </div>
              )}

              {meta.frames !== undefined && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Frames
                  </h3>
                  <p className="text-gray-900">{meta.frames.toLocaleString()}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {tx.status === 'PENDING' ? 'Reserved Amount' : 'Total Cost'}
                </h3>
                <p className={tx.status === 'PENDING' ? 'text-gray-500 italic' : ''}>
                  <AmountDisplay amountUsd={tx.amount_usd} className={tx.status === 'PENDING' ? 'text-gray-500' : ''} />
                  {tx.status === 'PENDING' && <span className="text-xs ml-1">(pending)</span>}
                </p>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Created At
                </h3>
                <p className="text-gray-900">{formatDateTime(tx.created_at)}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
  );
}
