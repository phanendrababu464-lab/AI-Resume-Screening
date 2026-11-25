import React from 'react';
import { Award, CheckCircle2, AlertCircle, AlertTriangle, ArrowUpRight } from 'lucide-react';
import type { Recommendation, CandidateRanking } from '../../types/api.ts';
import { formatPercent, formatPts, buildRecommendationSentence } from '../../utils/helpers.ts';

interface BestMatchHeroProps {
  recommendation: Recommendation;
  topCandidate?: CandidateRanking;
  totalCandidates: number;
  onOpenDetail?: (candidateName: string) => void;
}

export const BestMatchHero: React.FC<BestMatchHeroProps> = ({
  recommendation,
  topCandidate,
  onOpenDetail,
}) => {
  const {
    best_candidate,
    best_score,
    runner_up,
    margin_over_runner_up,
    strengths,
    gaps,
    warnings,
  } = recommendation;

  if (!best_candidate || best_score === null) {
    return null;
  }

  // Calculate SVG circular stroke
  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - ((best_score || 0) / 100) * circumference;

  // Check if no candidate meets all required skills
  const hasNoFullMatchWarning = warnings.some((w) =>
    w.toLowerCase().includes('no candidate fully meets')
  );

  return (
    <div className="bg-white dark:bg-midnight-surface border border-slate-200 dark:border-midnight-border rounded-2xl p-6 sm:p-7 shadow-card transition-colors relative overflow-hidden">
      {/* Background soft glow accent */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-accent-500/5 dark:bg-midnight-primary/10 rounded-full blur-3xl pointer-events-none" />

      {/* Amber alert if no candidate meets all required skills */}
      {hasNoFullMatchWarning && (
        <div className="mb-5 p-3.5 bg-amber-50 dark:bg-midnight-secondary/40 border border-amber-200 dark:border-midnight-secondary rounded-xl flex items-start space-x-2.5 text-xs text-amber-800 dark:text-midnight-hover">
          <AlertTriangle className="w-4 h-4 text-amber-500 dark:text-midnight-hover flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Cohort Requirement Shortfall:</span> No candidate in this batch fully meets all mandatory required skills. The recommendation below represents the best available candidate match.
          </div>
        </div>
      )}

      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        {/* Left: Candidate Details & Summary */}
        <div className="flex-1 space-y-3">
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-accent-50 text-accent-700 dark:bg-midnight-tint/80 dark:text-midnight-primary border border-accent-200 dark:border-midnight-secondary">
              <Award className="w-3.5 h-3.5 text-accent-500 dark:text-midnight-primary" />
              <span>Recommended Top Candidate</span>
            </span>
            {topCandidate?.below_min_experience && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-midnight-secondary/80 dark:text-midnight-hover border border-amber-200 dark:border-midnight-secondary">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 dark:text-midnight-hover" />
                <span>Below Minimum Experience</span>
              </span>
            )}
            {topCandidate?.is_duplicate && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-midnight-secondary/80 dark:text-midnight-hover border border-rose-200 dark:border-midnight-secondary">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-500 dark:text-midnight-hover" />
                <span>Probable Duplicate (matches {topCandidate.duplicate_of || 'another resume'})</span>
              </span>
            )}
          </div>

          <div>
            <h3 className="text-2xl font-extrabold text-slate-900 dark:text-midnight-ink tracking-tight flex items-center gap-2">
              <span>{best_candidate}</span>
              {onOpenDetail && (
                <button
                  onClick={() => onOpenDetail(best_candidate)}
                  className="text-xs text-accent-600 dark:text-midnight-primary font-semibold inline-flex items-center hover:underline ml-2"
                  aria-label={`View detailed breakdown for ${best_candidate}`}
                >
                  <span>View Details</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              )}
            </h3>
            {runner_up && margin_over_runner_up !== null && (
              <p className="text-xs text-slate-500 dark:text-midnight-muted mt-1">
                Margin over runner-up <strong className="text-slate-700 dark:text-midnight-muted">{runner_up}</strong>:{' '}
                <span className="font-mono font-bold text-emerald-600 dark:text-midnight-ink">
                  {formatPts(margin_over_runner_up)}
                </span>
              </p>
            )}
          </div>

          {/* Summary Text Callout */}
          <div className="p-3 bg-slate-50 dark:bg-midnight-canvas/60 border border-slate-200/80 dark:border-midnight-border rounded-xl text-xs text-slate-700 dark:text-midnight-muted leading-relaxed">
            <strong className="text-accent-600 dark:text-midnight-primary">Why this candidate: </strong>
            {buildRecommendationSentence(recommendation)}
          </div>
        </div>

        {/* Right: Large Score Ring */}
        <div className="flex-shrink-0 flex flex-col items-center justify-center p-3 sm:px-6">
          <div className="relative w-32 h-32 flex items-center justify-center">
            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 110 110">
              {/* Background track circle */}
              <circle
                cx="55"
                cy="55"
                r={radius}
                className="text-slate-100 dark:text-midnight-border"
                strokeWidth="10"
                stroke="currentColor"
                fill="transparent"
              />
              {/* Value stroke circle */}
              <circle
                cx="55"
                cy="55"
                r={radius}
                className="text-accent-600 dark:text-midnight-primary transition-all duration-1000 ease-out"
                strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-midnight-ink tracking-tight font-mono">
                {formatPercent(best_score, 1)}
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 dark:text-midnight-muted">
                Match Score
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Strengths, Gaps & Warnings */}
      <div className="mt-6 pt-5 border-t border-slate-100 dark:border-midnight-border/80 grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
        {/* Strengths */}
        <div className="space-y-1.5">
          <span className="font-bold text-slate-800 dark:text-midnight-ink flex items-center space-x-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 dark:text-midnight-ink" />
            <span>Key Strengths</span>
          </span>
          {strengths.length > 0 ? (
            <ul className="space-y-1 text-slate-600 dark:text-midnight-muted pl-5 list-disc">
              {strengths.map((s, idx) => (
                <li key={idx} className="leading-relaxed">
                  {s}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-400 dark:text-midnight-muted italic">None noted.</p>
          )}
        </div>

        {/* Gaps */}
        <div className="space-y-1.5">
          <span className="font-bold text-slate-800 dark:text-midnight-ink flex items-center space-x-1.5">
            <AlertCircle className="w-4 h-4 text-amber-500 dark:text-midnight-hover" />
            <span>Gaps & Unmatched Skills</span>
          </span>
          {gaps.length > 0 ? (
            <ul className="space-y-1 text-slate-600 dark:text-midnight-muted pl-5 list-disc">
              {gaps.map((g, idx) => (
                <li key={idx} className="leading-relaxed">
                  {g}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-slate-400 dark:text-midnight-muted italic">None — candidate meets requirements.</p>
          )}
        </div>

        {/* Warnings */}
        <div className="space-y-1.5">
          <span className="font-bold text-slate-800 dark:text-midnight-ink flex items-center space-x-1.5">
            <AlertTriangle className="w-4 h-4 text-rose-500 dark:text-midnight-hover" />
            <span>Advisory Warnings</span>
          </span>
          {warnings.length > 0 ? (
            <ul className="space-y-1 text-rose-700 dark:text-midnight-hover pl-5 list-disc font-medium">
              {warnings.map((w, idx) => (
                <li key={idx} className="leading-relaxed">
                  {w}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-emerald-600 dark:text-midnight-ink flex items-center space-x-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>No critical warnings detected.</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
