import React from 'react';
import { ThumbsUp, ThumbsDown, CheckCircle2, XCircle } from 'lucide-react';
import { ClaimWithEvidence } from '../types/intelligence';

interface GroundedClaimsProps {
  pros: ClaimWithEvidence[];
  cons: ClaimWithEvidence[];
}

interface ClaimListProps {
  claims: ClaimWithEvidence[];
  tone: 'emerald' | 'rose';
  emptyLabel: string;
}

const ClaimList: React.FC<ClaimListProps> = ({ claims, tone, emptyLabel }) => {
  const isPros = tone === 'emerald';

  if (!claims.length) {
    return <p className="text-xs text-slate-400 italic">{emptyLabel}</p>;
  }

  return (
    <ul className="space-y-3">
      {claims.map((claim) => (
        <li
          key={claim.claim}
          className={`rounded-xl border p-3.5 space-y-2 ${
            isPros ? 'border-emerald-200 bg-emerald-50/60' : 'border-rose-200 bg-rose-50/60'
          }`}
        >
          <div className="flex items-start gap-2">
            {isPros ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
            ) : (
              <XCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
            )}
            <span className="text-xs font-bold text-slate-900">{claim.claim}</span>
          </div>

          <div className="space-y-1.5 pl-6">
            {claim.evidence.map((item) => (
              <div key={item.review_id} className="flex items-start gap-1.5">
                <span
                  className={`font-mono text-[10px] shrink-0 mt-0.5 ${
                    isPros ? 'text-emerald-700' : 'text-rose-700'
                  }`}
                >
                  [{item.review_id}]
                </span>
                <span
                  className={`text-[11px] italic leading-snug ${
                    isPros ? 'text-emerald-900' : 'text-rose-900'
                  }`}
                >
                  “{item.excerpt}”
                </span>
              </div>
            ))}
          </div>

          <div className="pl-6">
            <span
              className={`text-[10px] font-bold uppercase tracking-wide ${
                isPros ? 'text-emerald-700' : 'text-rose-700'
              }`}
            >
              Supported by {claim.support_count} {claim.support_count === 1 ? 'review' : 'reviews'}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
};

/**
 * Pros and cons where every claim carries validated evidence. The backend
 * drops any claim it cannot trace to a real review, so anything rendered here
 * has at least one citation by construction.
 */
export const GroundedClaims: React.FC<GroundedClaimsProps> = ({ pros, cons }) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="modern-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h4 className="text-sm font-bold text-emerald-800 flex items-center gap-2">
            <ThumbsUp className="h-4 w-4 text-emerald-600" />
            Pros (evidence-backed)
          </h4>
          <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
            {pros.length}
          </span>
        </div>
        <ClaimList claims={pros} tone="emerald" emptyLabel="No evidence-backed pros found in these reviews." />
      </div>

      <div className="modern-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h4 className="text-sm font-bold text-rose-800 flex items-center gap-2">
            <ThumbsDown className="h-4 w-4 text-rose-600" />
            Cons (evidence-backed)
          </h4>
          <span className="text-xs font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
            {cons.length}
          </span>
        </div>
        <ClaimList claims={cons} tone="rose" emptyLabel="No evidence-backed cons found in these reviews." />
      </div>
    </div>
  );
};
