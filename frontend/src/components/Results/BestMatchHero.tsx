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
    <div className="bg-theme-surface border border-theme-border rounded-2xl p-6 sm:p-7 shadow-card transition-colors relative overflow-hidden">
      {/* Background soft glow accent */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-theme-primary/10 rounded-full blur-3xl pointer-events-none" />

      {/* Amber alert if no candidate meets all required skills */}
      {hasNoFullMatchWarning && (
        <div className="mb-5 p-3.5 bg-theme-secondary/40 border border-theme-secondary rounded-xl flex items-start space-x-2.5 text-xs text-theme-hover">
          <AlertTriangle className="w-4 h-4 text-theme-hover flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Cohort Requirement Shortfall:</span> No candidate in this batch fully meets all mandatory required skills. The recommendation below represents the best available candidate match.
          </div>
        </div>
      )}

      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        {/* Left: Candidate Details & Summary */}
        <div className="flex-1 space-y-3">
          <div className="flex items-center space-x-2">
            <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-theme-tint/80 text-theme-primary border border-theme-secondary">
              <Award className="w-3.5 h-3.5 text-theme-primary" />
              <span>Recommended Top Candidate</span>
            </span>
            {topCandidate?.below_min_experience && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-theme-secondary/80 text-theme-hover border border-theme-secondary">
                <AlertTriangle className="w-3.5 h-3.5 text-theme-hover" />
                <span>Below Minimum Experience</span>
              </span>
            )}
            {topCandidate?.is_duplicate && (
              <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-theme-secondary/80 text-theme-hover border border-theme-secondary">
                <AlertTriangle className="w-3.5 h-3.5 text-theme-hover" />
                <span>Probable Duplicate (matches {topCandidate.duplicate_of || 'another resume'})</span>
              </span>
            )}
          </div>

          <div>
            <h3 className="text-2xl font-extrabold text-theme-ink tracking-tight flex items-center gap-2">
              <span>{best_candidate}</span>
              {onOpenDetail && (
                <button
                  onClick={() => onOpenDetail(best_candidate)}
                  className="text-xs text-theme-primary font-semibold inline-flex items-center hover:underline ml-2"
                  aria-label={`View detailed breakdown for ${best_candidate}`}
                >
                  <span>View Details</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </button>
              )}
            </h3>
            {runner_up && margin_over_runner_up !== null && (
              <p className="text-xs text-theme-secondary-text mt-1">
                Margin over runner-up <strong className="text-theme-secondary-text">{runner_up}</strong>:{' '}
                <span className="font-mono font-bold text-theme-ink">
                  {formatPts(margin_over_runner_up)}
                </span>
              </p>
            )}
          </div>

          {/* Summary Text Callout */}
          <div className="p-3 bg-theme-canvas/60 border border-theme-border rounded-xl text-xs text-theme-secondary-text leading-relaxed">
            <strong className="text-theme-primary">Why this candidate: </strong>
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
                className="text-theme-subtle"
                strokeWidth="10"
                stroke="currentColor"
                fill="transparent"
              />
              {/* Value stroke circle */}
              <circle
                cx="55"
                cy="55"
                r={radius}
                className="text-theme-primary transition-all duration-1000 ease-out"
                strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                stroke="currentColor"
                fill="transparent"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="text-2xl sm:text-3xl font-extrabold text-theme-ink tracking-tight font-mono">
                {formatPercent(best_score, 1)}
              </span>
              <span className="text-[10px] uppercase font-bold tracking-wider text-theme-secondary-text">
                Match Score
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Strengths, Gaps & Warnings */}
      <div className="mt-6 pt-5 border-t border-theme-border/80 grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
        {/* Strengths */}
        <div className="space-y-1.5">
          <span className="font-bold text-theme-ink flex items-center space-x-1.5">
            <CheckCircle2 className="w-4 h-4 text-theme-ink" />
            <span>Key Strengths</span>
          </span>
          {strengths.length > 0 ? (
            <ul className="space-y-1 text-theme-secondary-text pl-5 list-disc">
              {strengths.map((s, idx) => (
                <li key={idx} className="leading-relaxed">
                  {s}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-theme-secondary-text italic">None noted.</p>
          )}
        </div>

        {/* Gaps */}
        <div className="space-y-1.5">
          <span className="font-bold text-theme-ink flex items-center space-x-1.5">
            <AlertCircle className="w-4 h-4 text-theme-hover" />
            <span>Gaps & Unmatched Skills</span>
          </span>
          {gaps.length > 0 ? (
            <ul className="space-y-1 text-theme-secondary-text pl-5 list-disc">
              {gaps.map((g, idx) => (
                <li key={idx} className="leading-relaxed">
                  {g}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-theme-secondary-text italic">None — candidate meets requirements.</p>
          )}
        </div>

        {/* Warnings */}
        <div className="space-y-1.5">
          <span className="font-bold text-theme-ink flex items-center space-x-1.5">
            <AlertTriangle className="w-4 h-4 text-theme-hover" />
            <span>Advisory Warnings</span>
          </span>
          {warnings.length > 0 ? (
            <ul className="space-y-1 text-theme-hover pl-5 list-disc font-medium">
              {warnings.map((w, idx) => (
                <li key={idx} className="leading-relaxed">
                  {w}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-theme-ink flex items-center space-x-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>No critical warnings detected.</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
