import React from 'react';
import { Trophy, AlertTriangle, ArrowRight } from 'lucide-react';
import type { CandidateRanking } from '../../types/api.ts';
import { formatPercent } from '../../utils/helpers.ts';

interface LeaderboardProps {
  rankings: CandidateRanking[];
  onSelectCandidate: (candidateName: string) => void;
  selectedCandidate: string | null;
}

export const Leaderboard: React.FC<LeaderboardProps> = ({
  rankings,
  onSelectCandidate,
  selectedCandidate,
}) => {
  return (
    <div className="bg-theme-surface border border-theme-border rounded-2xl p-6 shadow-card transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-theme-border/80 mb-5">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-theme-tint/60 text-theme-primary flex items-center justify-center">
            <Trophy className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-theme-ink uppercase tracking-wider">
              Candidate Leaderboard
            </h3>
            <p className="text-xs text-theme-secondary-text">
              Ranked descending by composite match score
            </p>
          </div>
        </div>
        <span className="text-xs text-theme-secondary-text font-medium hidden sm:inline">
          Click any row to open candidate detail drawer
        </span>
      </div>

      <div className="space-y-3">
        {rankings.map((candidate) => {
          const isTop = candidate.rank === 1;
          const isSelected = selectedCandidate === candidate.candidate;
          const scorePercent = Math.min(100, Math.max(0, candidate.match_score));

          return (
            <div
              key={candidate.candidate}
              onClick={() => onSelectCandidate(candidate.candidate)}
              className={`group p-3.5 rounded-xl border transition-all cursor-pointer ${
                isSelected
                  ? 'border-theme-primary bg-theme-tint/30 shadow-sm'
                  : 'border-theme-border hover:border-theme-hover bg-theme-canvas/30'
              }`}
              role="button"
              tabIndex={0}
              aria-label={`View details for rank ${candidate.rank} ${candidate.candidate}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  onSelectCandidate(candidate.candidate);
                }
              }}
            >
              <div className="flex items-center justify-between gap-3 mb-2">
                {/* Candidate Rank & Name */}
                <div className="flex items-center space-x-2.5 min-w-0">
                  <span
                    className={`min-w-6 h-6 px-1.5 rounded-full flex items-center justify-center text-xs font-bold font-mono ${
                      isTop
                        ? 'bg-theme-hover text-theme-on-accent shadow-sm'
                        : 'bg-theme-subtle text-theme-secondary-text'
                    }`}
                  >
                    #{candidate.rank_display || candidate.rank}
                  </span>
                  <span className="font-semibold text-sm text-theme-ink truncate" title={candidate.candidate}>
                    {candidate.candidate}
                  </span>

                  {/* Below Min Experience Badge */}
                  {candidate.below_min_experience && (
                    <span
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-theme-secondary/40 text-theme-hover border border-theme-secondary"
                      title="Experience is below minimum requirement. Penalty applied."
                    >
                      <AlertTriangle className="w-3 h-3 text-theme-hover" />
                      <span>Below Min Exp</span>
                    </span>
                  )}

                  {/* Probable Duplicate Badge */}
                  {candidate.is_duplicate && (
                    <span
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-theme-secondary/40 text-theme-hover border border-theme-secondary"
                      title={`Probable duplicate: exact text match with ${candidate.duplicate_of || 'another candidate'}`}
                    >
                      <AlertTriangle className="w-3 h-3 text-theme-hover" />
                      <span>Duplicate ({candidate.duplicate_of || 'matches another'})</span>
                    </span>
                  )}
                </div>

                {/* Score & View details link */}
                <div className="flex items-center space-x-3 flex-shrink-0">
                  <span className="font-mono font-bold text-base text-theme-ink">
                    {formatPercent(candidate.match_score, 1)}
                  </span>
                  <ArrowRight className="w-4 h-4 text-theme-secondary-text group-hover:text-theme-hover group-hover:translate-x-0.5 transition" />
                </div>
              </div>

              {/* Progress Bar with readable percentage printed inside or at the end */}
              <div className="relative w-full bg-theme-subtle h-3 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    isTop
                      ? 'bg-theme-ink'
                      : candidate.below_min_experience
                      ? 'bg-theme-hover'
                      : 'bg-theme-primary'
                  }`}
                  style={{ width: `${scorePercent}%` }}
                />
              </div>

              {/* Quick skill stats footer */}
              <div className="mt-2 flex items-center justify-between text-[11px] text-theme-secondary-text">
                <span>
                  Req Skills: <strong>{candidate.matched_required_skills.length}</strong> matched,{' '}
                  <span className={candidate.missing_required_skills.length > 0 ? 'text-theme-hover font-medium' : ''}>
                    {candidate.missing_required_skills.length} missing
                  </span>
                </span>
                {candidate.related_skills_matched.length > 0 && (
                  <span className="text-theme-hover font-medium">
                    ≈ {candidate.related_skills_matched.length} related match{candidate.related_skills_matched.length > 1 ? 'es' : ''}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
