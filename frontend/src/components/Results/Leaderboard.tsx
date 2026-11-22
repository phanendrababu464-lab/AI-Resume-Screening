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
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-card transition-colors">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800/80 mb-5">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-accent-50 text-accent-600 dark:bg-accent-950/60 dark:text-accent-400 flex items-center justify-center">
            <Trophy className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Candidate Leaderboard
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Ranked descending by composite match score
            </p>
          </div>
        </div>
        <span className="text-xs text-slate-400 font-medium hidden sm:inline">
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
                  ? 'border-accent-500 bg-accent-50/40 dark:bg-accent-950/30 shadow-sm'
                  : 'border-slate-200/80 dark:border-slate-800 hover:border-accent-400 dark:hover:border-accent-600 bg-slate-50/30 dark:bg-slate-950/30'
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
                        ? 'bg-amber-400 text-slate-950 shadow-sm'
                        : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    #{candidate.rank_display || candidate.rank}
                  </span>
                  <span className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate" title={candidate.candidate}>
                    {candidate.candidate}
                  </span>

                  {/* Below Min Experience Badge */}
                  {candidate.below_min_experience && (
                    <span
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                      title="Experience is below minimum requirement. Penalty applied."
                    >
                      <AlertTriangle className="w-3 h-3 text-amber-600 dark:text-amber-400" />
                      <span>Below Min Exp</span>
                    </span>
                  )}

                  {/* Probable Duplicate Badge */}
                  {candidate.is_duplicate && (
                    <span
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                      title={`Probable duplicate: exact text match with ${candidate.duplicate_of || 'another candidate'}`}
                    >
                      <AlertTriangle className="w-3 h-3 text-rose-600 dark:text-rose-400" />
                      <span>Duplicate ({candidate.duplicate_of || 'matches another'})</span>
                    </span>
                  )}
                </div>

                {/* Score & View details link */}
                <div className="flex items-center space-x-3 flex-shrink-0">
                  <span className="font-mono font-bold text-base text-slate-900 dark:text-slate-100">
                    {formatPercent(candidate.match_score, 1)}
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-400 group-hover:text-accent-500 group-hover:translate-x-0.5 transition" />
                </div>
              </div>

              {/* Progress Bar with readable percentage printed inside or at the end */}
              <div className="relative w-full bg-slate-200 dark:bg-slate-800 h-3 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    isTop
                      ? 'bg-emerald-500 dark:bg-emerald-400'
                      : candidate.below_min_experience
                      ? 'bg-amber-500 dark:bg-amber-400'
                      : 'bg-accent-600 dark:bg-accent-500'
                  }`}
                  style={{ width: `${scorePercent}%` }}
                />
              </div>

              {/* Quick skill stats footer */}
              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>
                  Req Skills: <strong>{candidate.matched_required_skills.length}</strong> matched,{' '}
                  <span className={candidate.missing_required_skills.length > 0 ? 'text-rose-500 font-medium' : ''}>
                    {candidate.missing_required_skills.length} missing
                  </span>
                </span>
                {candidate.related_skills_matched.length > 0 && (
                  <span className="text-amber-600 dark:text-amber-400 font-medium">
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
