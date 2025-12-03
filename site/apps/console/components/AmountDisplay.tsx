import React from 'react';

interface AmountDisplayProps {
  amountUsd: string;
  className?: string;
  showSign?: boolean;
}

export default function AmountDisplay({ amountUsd, className = '' }: AmountDisplayProps) {
  const amount = parseFloat(amountUsd);
  const isPositive = amount >= 0;
  const colorClass = isPositive ? 'text-green-600' : 'text-gray-900';
  const absAmount = amountUsd.replace('-', '');

  return (
    <span className={`${colorClass} ${className}`}>
      ${absAmount}
    </span>
  );
}
