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

interface InvoiceTransactionRowProps {
  tx: Transaction;
  isExpanded: boolean;
  onToggle: () => void;
}

export default function InvoiceTransactionRow({ tx, isExpanded, onToggle }: InvoiceTransactionRowProps) {
  const meta = tx.meta || {};

  const getInvoiceStatusInfo = () => {
    const status = tx.status.toLowerCase();
    if (status === 'completed') return { label: 'paid', class: 'bg-green-100 text-green-800 border-green-200' };
    if (status === 'processing') return { label: 'processing', class: 'bg-yellow-100 text-yellow-800 border-yellow-200' };
    if (status === 'pending') return { label: 'Pending', class: 'bg-gray-100 text-gray-800 border-gray-200' };
    if (status === 'failed') return { label: 'voided', class: 'bg-red-100 text-red-800 border-red-200' };
    return { label: status, class: 'bg-gray-100 text-gray-800 border-gray-200' };
  };

  const invoiceStatus = getInvoiceStatusInfo();

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
            {meta.invoice_id || tx.id.slice(0, 8) + '...'}
          </span>
        </td>
        <td className="px-6 py-4 whitespace-nowrap w-28">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-blue-100 text-blue-800 border-blue-200">
              invoice
            </span>
          </div>
        </td>
        <td className="px-6 py-4 whitespace-nowrap">
          {meta.payment_method ? (
            <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border bg-gray-100 text-gray-800 border-gray-200">
              {meta.payment_method === 'bank_transfer' || meta.payment_method === 'wire' ? 'Wire' : meta.payment_method}
            </span>
          ) : (
            <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${invoiceStatus.class}`}>
              {invoiceStatus.label}
            </span>
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
              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Transaction ID
                </h3>
                <p className="font-mono text-sm text-gray-900">{tx.id}</p>
              </div>

              {meta.invoice_id && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Invoice ID
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{meta.invoice_id}</p>
                </div>
              )}

              {meta.invoice_uuid && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Invoice UUID
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{meta.invoice_uuid}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Status
                </h3>
                <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded border ${getBadgeClass(tx.status)}`}>
                  {tx.status.toLowerCase()}
                </span>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Amount
                </h3>
                <AmountDisplay amountUsd={tx.amount_usd} className="font-semibold" />
              </div>

              {meta.invoice_amount_usd && meta.invoice_amount_usd !== tx.amount_usd && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Invoice Amount
                  </h3>
                  <p className="text-gray-900">${meta.invoice_amount_usd}</p>
                </div>
              )}

              {meta.payment_method && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Payment Method
                  </h3>
                  <p className="text-gray-900">{meta.payment_method}</p>
                </div>
              )}

              {meta.reference && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Reference
                  </h3>
                  <p className="font-mono text-sm text-gray-900">{meta.reference}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Created At
                </h3>
                <p className="text-gray-900">{formatDateTime(tx.created_at)}</p>
              </div>

              {tx.updated_at && tx.updated_at !== tx.created_at && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-2">
                    Updated At
                  </h3>
                  <p className="text-gray-900">{formatDateTime(tx.updated_at)}</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
  );
}
