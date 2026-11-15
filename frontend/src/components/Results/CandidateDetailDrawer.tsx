import React from 'react';
import { X, Award, AlertTriangle, CheckCircle2, Layers, Cpu, Clock, FileText } from 'lucide-react';
import type { CandidateRanking } from '../../types/api.ts';
import { formatPercent } from '../../utils/helpers.ts';

interface CandidateDetailDrawerProps {
  candidate: CandidateRanking | null;
  onClose: () => void;
}

export const CandidateDetailDrawer: React.FC<CandidateDetailDrawerProps> = ({
  candidate,
  onClose,
}) => {
  if (!candidate) return null;

  const cs = candidate.component_scores;

  const components = [
    {
      name: 'Required Skill Coverage',
      score: cs.required_skill_score !== null ? cs.required_skill_score * 100 : null,
      icon: CheckCircle2,
      color: 'bg-accent-500',
    },
    {
      name: 'Preferred Skill Coverage',
      score: cs.preferred_skill_score !== null ? cs.preferred_skill_score * 100 : null,
      icon: Layers,
      color: 'bg-purple-500',
    },
    {
      name: 'Semantic Similarity',
      score: cs.semantic_score !== null ? cs.semantic_score * 100 : null,
      icon: Cpu,
      color: 'bg-emerald-500',
    },
    {
      name: 'Experience Alignment',
      score: cs.experience_score !== null ? cs.experience_score * 100 : null,
      icon: Clock,
      color: 'bg-amber-500',
    },
    {
      name: 'TF-IDF Baseline Match',
      score: cs.tfidf_baseline_score !== null && cs.tfidf_baseline_score !== undefined ? cs.tfidf_baseline_score * 100 : null,
      icon: FileText,
      color: 'bg-slate-500',
    },
  ];

  return (
    <div
      className="fixed inset-0 w-screen h-screen z-50 overflow-hidden"
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
    >
      {/* Full-viewport fixed backdrop overlay: covers full screen on scroll & click closes drawer */}
      <div
        className="fixed inset-0 w-screen h-screen bg-slate-900/60 backdrop-blur-xs transition-opacity cursor-pointer"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out drawer container anchored to right */}
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10 z-10 pointer-events-none">
        <div className="w-screen max-w-lg bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 h-full shadow-2xl flex flex-col justify-between overflow-y-auto animate-slide-left pointer-events-auto">
          <div>
            {/* Header */}
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="min-w-6 h-6 px-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center font-bold text-xs font-mono">
                    #{candidate.rank_display || candidate.rank}
                  </span>
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                    Candidate Detail Card
                  </span>
                </div>
                <h3 id="drawer-title" className="text-xl font-bold text-slate-900 dark:text-slate-100 truncate max-w-sm">
                  {candidate.candidate}
                </h3>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                aria-label="Close candidate drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Score Ring / Composite Metric Banner */}
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-xs uppercase font-bold text-slate-400 dark:text-slate-500">
                    Composite Match Score
                  </span>
                  <div className="text-3xl font-extrabold font-mono text-accent-600 dark:text-accent-400 mt-0.5">
                    {formatPercent(candidate.match_score, 1)}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  {candidate.below_min_experience && (
                    <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800 text-xs font-semibold">
                      <AlertTriangle className="w-4 h-4 text-amber-500" />
                      <span>Below Min Exp</span>
                    </div>
                  )}
                  {candidate.is_duplicate && (
                    <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-300 dark:border-rose-800 text-xs font-semibold">
                      <AlertTriangle className="w-4 h-4 text-rose-500" />
                      <span>Probable Duplicate</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 5 Component Bars */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                  Evaluation Component Breakdown
                </h4>
                <div className="space-y-2.5">
                  {components.map((comp) => (
                    <div key={comp.name} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="flex items-center space-x-1.5 font-medium text-slate-700 dark:text-slate-300">
                          <comp.icon className="w-3.5 h-3.5 text-slate-400" />
                          <span>{comp.name}</span>
                        </span>
                        <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                          {formatPercent(comp.score, 1)}
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${comp.color} rounded-full transition-all duration-500`}
                          style={{ width: `${comp.score !== null ? Math.min(100, Math.max(0, comp.score)) : 0}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            {/* Skills Taxonomy Section */}
            <div className="space-y-4 pt-2">
              <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                Skill Taxonomy Breakdown
              </h4>

              {/* Matched Required Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Matched Required Skills ({candidate.matched_required_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.matched_required_skills.length > 0 ? (
                    candidate.matched_required_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800 text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-400 italic">None matched</span>
                  )}
                </div>
              </div>

              {/* Matched Preferred Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-purple-600 dark:text-purple-400 flex items-center space-x-1">
                  <Layers className="w-3.5 h-3.5" />
                  <span>Matched Preferred Skills ({candidate.matched_preferred_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.matched_preferred_skills.length > 0 ? (
                    candidate.matched_preferred_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md bg-purple-50 text-purple-800 border border-purple-200 dark:bg-purple-950/60 dark:text-purple-300 dark:border-purple-800 text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-400 italic">None matched</span>
                  )}
                </div>
              </div>

              {/* Related Skills Matched */}
              {candidate.related_skills_matched.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-xs font-semibold text-amber-600 dark:text-amber-400 flex items-center space-x-1">
                    <Award className="w-3.5 h-3.5" />
                    <span>Related Skills Partial Credit ({candidate.related_skills_matched.length})</span>
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {candidate.related_skills_matched.map((r, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800 text-xs font-medium"
                      >
                        ≈ {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing Required Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 flex items-center space-x-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Missing Required Skills ({candidate.missing_required_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.missing_required_skills.length > 0 ? (
                    candidate.missing_required_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800 text-xs font-medium"
                      >
                        ✗ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                      ✓ Possesses all mandatory required skills!
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-100 dark:border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="w-full py-2.5 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 rounded-xl text-xs font-semibold transition"
          >
            Close Detail Drawer
          </button>
        </div>
      </div>
    </div>
  </div>
  );
};
