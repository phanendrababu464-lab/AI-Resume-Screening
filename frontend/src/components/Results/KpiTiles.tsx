import React from 'react';
import { Trophy, Users, AlertTriangle, TrendingUp } from 'lucide-react';
import type { ScreenResponse } from '../../types/api.ts';
import { formatPercent } from '../../utils/helpers.ts';

interface KpiTilesProps {
  results: ScreenResponse;
}

export const KpiTiles: React.FC<KpiTilesProps> = ({ results }) => {
  const { rankings, total_candidates } = results;

  if (!rankings || rankings.length === 0) return null;

  const topCandidate = rankings[0];
  const bestScore = topCandidate ? topCandidate.match_score : 0;

  // Shortfalls: candidates with below_min_experience OR missing mandatory required skills
  const shortfalls = rankings.filter(
    (r) => r.below_min_experience || (r.missing_required_skills && r.missing_required_skills.length > 0)
  ).length;

  // Cohort average score
  const totalScoreSum = rankings.reduce((acc, curr) => acc + curr.match_score, 0);
  const averageScore = rankings.length > 0 ? totalScoreSum / rankings.length : 0;

  const kpis = [
    {
      id: 'best_score',
      label: 'Best Candidate Match',
      value: formatPercent(bestScore, 1),
      subtitle: topCandidate ? topCandidate.candidate : 'N/A',
      icon: Trophy,
      colorClass: 'text-sky-600 dark:text-midnight-primary',
      bgClass: 'bg-sky-50 dark:bg-midnight-tint/50 border-sky-200 dark:border-midnight-border',
    },
    {
      id: 'screened_count',
      label: 'Candidates Screened',
      value: `${total_candidates}`,
      subtitle: `${total_candidates} parsed & evaluated`,
      icon: Users,
      colorClass: 'text-indigo-600 dark:text-midnight-primary',
      bgClass: 'bg-indigo-50 dark:bg-midnight-tint/50 border-indigo-200 dark:border-midnight-border',
    },
    {
      id: 'shortfalls',
      label: 'Requirement Shortfalls',
      value: `${shortfalls}`,
      subtitle: shortfalls === 0 ? 'All meet criteria' : `${shortfalls} gap${shortfalls > 1 ? 's' : ''} detected`,
      icon: AlertTriangle,
      colorClass: shortfalls > 0 ? 'text-amber-600 dark:text-midnight-hover' : 'text-emerald-600 dark:text-midnight-ink',
      bgClass:
        shortfalls > 0
          ? 'bg-amber-50 dark:bg-midnight-secondary/50 border-amber-200 dark:border-midnight-secondary'
          : 'bg-emerald-50 dark:bg-midnight-tint/50 border-emerald-200 dark:border-midnight-border',
    },
    {
      id: 'average_score',
      label: 'Cohort Average Score',
      value: formatPercent(averageScore, 1),
      subtitle: `Across ${rankings.length} evaluated resumes`,
      icon: TrendingUp,
      colorClass: 'text-emerald-600 dark:text-midnight-ink',
      bgClass: 'bg-emerald-50 dark:bg-midnight-tint/50 border-emerald-200 dark:border-midnight-border',
    },
  ];

  return (
    <div
      id="results-kpi"
      className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4"
      role="region"
      aria-label="Evaluation Key Performance Indicators"
    >
      {kpis.map((kpi) => {
        const Icon = kpi.icon;
        return (
          <div
            key={kpi.id}
            className="p-4 rounded-xl border border-slate-200 dark:border-midnight-border bg-white dark:bg-midnight-surface shadow-sm flex flex-col justify-between transition-colors"
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-[11px] font-semibold text-slate-500 dark:text-midnight-muted uppercase tracking-wider truncate">
                {kpi.label}
              </span>
              <div className={`w-7 h-7 rounded-lg border ${kpi.bgClass} flex items-center justify-center shrink-0`}>
                <Icon className={`w-3.5 h-3.5 ${kpi.colorClass}`} />
              </div>
            </div>
            <div>
              <div className="text-xl sm:text-2xl font-black font-mono text-slate-900 dark:text-midnight-ink tracking-tight">
                {kpi.value}
              </div>
              <div className="text-xs text-slate-500 dark:text-midnight-muted truncate mt-0.5" title={kpi.subtitle}>
                {kpi.subtitle}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
