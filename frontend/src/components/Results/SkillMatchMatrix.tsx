import React from 'react';
import { Target, Sparkles } from 'lucide-react';
import type { SkillMatrixItem, CandidateRanking, JobAnalysis } from '../../types/api.ts';
import { parseRelatedSkillMatch } from '../../utils/helpers.ts';

interface SkillMatchMatrixProps {
  matrixData: SkillMatrixItem[];
  rankings: CandidateRanking[];
  job: JobAnalysis;
  onSelectCandidate?: (candidateName: string) => void;
}

export const SkillMatchMatrix: React.FC<SkillMatchMatrixProps> = ({
  matrixData,
  rankings,
  job,
  onSelectCandidate,
}) => {
  if (!matrixData || matrixData.length === 0 || (!job.required_skills?.length && !job.preferred_skills?.length)) {
    return (
      <div className="bg-white dark:bg-midnight-surface border border-slate-200 dark:border-midnight-border rounded-2xl p-6 text-center text-xs text-slate-500 dark:text-midnight-muted">
        No specific required or preferred skills extracted to display in the matrix.
      </div>
    );
  }

  // Extract unique required and preferred skills preserving order
  const reqSkills = Array.from(new Set(job.required_skills || []));
  const prefSkills = Array.from(new Set(job.preferred_skills || [])).filter(
    (s) => !reqSkills.includes(s)
  );
  const allSkills = [...reqSkills, ...prefSkills];
  const hasPref = prefSkills.length > 0;

  // Build lookup map: (candidate, skill) -> status
  const statusMap = new Map<string, 'Exact Match' | 'Related Match' | 'Missing'>();
  for (const item of matrixData) {
    statusMap.set(`${item.candidate}:::${item.skill}`, item.status);
  }

  // Stats calculation
  const totalExact = matrixData.filter((m) => m.status === 'Exact Match').length;
  const totalRelated = matrixData.filter((m) => m.status === 'Related Match').length;
  const totalMissing = matrixData.filter((m) => m.status === 'Missing').length;

  return (
    <div className="bg-white dark:bg-midnight-surface border border-slate-200 dark:border-midnight-border rounded-2xl p-6 shadow-card transition-colors">
      {/* Header & Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 dark:border-midnight-border/80 mb-4 gap-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-accent-50 text-accent-600 dark:bg-midnight-tint/60 dark:text-midnight-primary flex items-center justify-center">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-midnight-ink uppercase tracking-wider">
              Skill Match Matrix
            </h3>
            <p className="text-xs text-slate-500 dark:text-midnight-muted">
              Candidate skills matched against job taxonomy requirements
            </p>
          </div>
        </div>

        {/* Compact Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded bg-emerald-100 border border-emerald-500 text-emerald-800 dark:bg-midnight-tint dark:border-midnight-ink dark:text-midnight-ink flex items-center justify-center font-bold text-xs">
              ✓
            </span>
            <span className="text-slate-600 dark:text-midnight-muted font-medium">Exact Match (1.0)</span>
          </span>

          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded bg-amber-100 border border-amber-500 text-amber-800 dark:bg-midnight-secondary/40 dark:border-midnight-hover dark:text-midnight-hover flex items-center justify-center font-bold text-xs">
              ≈
            </span>
            <span className="text-slate-600 dark:text-midnight-muted font-medium">Related Match (Partial)</span>
          </span>

          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded bg-rose-100 border border-rose-500 text-rose-800 dark:bg-midnight-secondary/40 dark:border-midnight-hover dark:text-midnight-hover flex items-center justify-center font-bold text-xs">
              ✗
            </span>
            <span className="text-slate-600 dark:text-midnight-muted font-medium">Missing (0.0)</span>
          </span>
        </div>
      </div>

      {/* Responsive Horizontal Scroll Wrapper */}
      <div className="w-full overflow-x-auto rounded-xl border border-slate-200 dark:border-midnight-border bg-white dark:bg-midnight-surface shadow-sm">
        <table className="w-max min-w-full border-collapse text-xs select-none">
          <thead>
            {/* Tier 1: Group Headers */}
            <tr className="border-b border-slate-200 dark:border-midnight-border">
              <th
                rowSpan={2}
                className="sticky left-0 z-20 bg-slate-50 dark:bg-midnight-canvas p-3.5 text-left font-bold text-slate-800 dark:text-midnight-ink border-r-2 border-slate-300 dark:border-midnight-border w-44 min-w-[170px]"
              >
                Candidate
              </th>
              {reqSkills.length > 0 && (
                <th
                  colSpan={reqSkills.length}
                  className={`bg-accent-50/80 dark:bg-midnight-tint/40 text-accent-700 dark:text-midnight-primary font-bold uppercase tracking-wider py-2 text-center text-[11px] ${
                    hasPref ? 'border-r-2 border-slate-400 dark:border-midnight-border' : ''
                  }`}
                >
                  REQUIRED SKILLS ({reqSkills.length})
                </th>
              )}
              {hasPref && (
                <th
                  colSpan={prefSkills.length}
                  className="bg-purple-50/80 dark:bg-midnight-tint/40 text-purple-700 dark:text-midnight-muted font-bold uppercase tracking-wider py-2 text-center text-[11px]"
                >
                  PREFERRED SKILLS ({prefSkills.length})
                </th>
              )}
              <th
                rowSpan={2}
                className="bg-slate-50 dark:bg-midnight-canvas p-3 text-center font-bold text-slate-800 dark:text-midnight-ink w-36 min-w-[130px]"
              >
                Match Summary
              </th>
            </tr>

            {/* Tier 2: Skill Names */}
            <tr className="border-b-2 border-slate-200 dark:border-midnight-border bg-slate-50/50 dark:bg-midnight-canvas/50">
              {reqSkills.map((s, idx) => {
                const isLastReq = idx === reqSkills.length - 1 && hasPref;
                return (
                  <th
                    key={s}
                    title={s}
                    className={`p-2 text-center font-semibold text-slate-700 dark:text-midnight-muted w-20 min-w-[70px] max-w-[80px] break-words leading-tight ${
                      isLastReq ? 'border-r-2 border-slate-400 dark:border-midnight-border' : 'border-r border-slate-200/60 dark:border-midnight-border'
                    }`}
                  >
                    <div className="line-clamp-2 text-[11px]">{s}</div>
                  </th>
                );
              })}
              {prefSkills.map((s) => (
                <th
                  key={s}
                  title={s}
                  className="p-2 text-center font-semibold text-slate-700 dark:text-midnight-muted w-20 min-w-[70px] max-w-[80px] break-words leading-tight border-r border-slate-200/60 dark:border-midnight-border"
                >
                  <div className="line-clamp-2 text-[11px]">{s}</div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 dark:divide-midnight-border/80">
            {rankings.map((cand) => {
              // Find related match info
              const reqMatchedCount = reqSkills.filter((s) => cand.matched_required_skills.includes(s)).length;
              const reqPct = reqSkills.length > 0 ? Math.round((reqMatchedCount / reqSkills.length) * 100) : 0;
              const prefMatchedCount = prefSkills.filter((s) => cand.matched_preferred_skills.includes(s)).length;

              return (
                <tr
                  key={cand.candidate}
                  className="hover:bg-slate-50/70 dark:hover:bg-midnight-tint/40 transition-colors h-[52px]"
                >
                  {/* Sticky Candidate Name */}
                  <td
                    className="sticky left-0 z-10 bg-white dark:bg-midnight-surface px-3.5 py-2 font-semibold text-slate-900 dark:text-midnight-ink border-r-2 border-slate-300 dark:border-midnight-border truncate max-w-[170px]"
                    title={cand.candidate}
                  >
                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] text-slate-400 dark:text-midnight-muted font-mono font-bold">#{cand.rank}</span>
                      <button
                        onClick={() => onSelectCandidate && onSelectCandidate(cand.candidate)}
                        className="truncate text-left hover:text-accent-600 dark:hover:text-midnight-hover transition"
                      >
                        {cand.candidate}
                      </button>
                    </div>
                  </td>

                  {/* Required Skills Cells */}
                  {reqSkills.map((s, idx) => {
                    const isLastReq = idx === reqSkills.length - 1 && hasPref;
                    const status = statusMap.get(`${cand.candidate}:::${s}`) || 'Missing';

                    // Find if there is a related match
                    const relEntry = cand.related_skills_matched.find(
                      (rel) => rel.toLowerCase().startsWith(s.toLowerCase() + ' (via ') || rel.toLowerCase().includes(s.toLowerCase())
                    );
                    const relParsed = relEntry ? parseRelatedSkillMatch(relEntry) : null;

                    return (
                      <td
                        key={s}
                        className={`p-1.5 text-center ${
                          isLastReq ? 'border-r-2 border-slate-400 dark:border-midnight-border' : 'border-r border-slate-100 dark:border-midnight-border'
                        }`}
                      >
                        <div
                          className={`w-11 h-11 mx-auto rounded-lg flex flex-col items-center justify-center font-bold transition shadow-xs ${
                            status === 'Exact Match'
                              ? 'bg-emerald-100/90 text-emerald-800 border border-emerald-400 dark:bg-midnight-tint/70 dark:border-midnight-ink dark:text-midnight-ink'
                              : status === 'Related Match'
                              ? 'bg-amber-100/90 text-amber-800 border border-amber-400 dark:bg-midnight-secondary/70 dark:border-midnight-hover dark:text-midnight-hover'
                              : 'bg-rose-100/80 text-rose-800 border border-rose-300 dark:bg-midnight-secondary/60 dark:border-midnight-secondary dark:text-midnight-hover'
                          }`}
                          title={
                            status === 'Related Match' && relParsed
                              ? `${cand.candidate} — ${s}: Related match via ${relParsed.sourceSkill} (${relParsed.weightPercent}% credit)`
                              : `${cand.candidate} — ${s}: ${status}`
                          }
                        >
                          <span className="text-base leading-none">
                            {status === 'Exact Match' ? '✓' : status === 'Related Match' ? '≈' : '✗'}
                          </span>
                          {status === 'Related Match' && relParsed && (
                            <span className="text-[8px] font-semibold truncate max-w-[38px] leading-tight mt-0.5">
                              {relParsed.displayLabel}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}

                  {/* Preferred Skills Cells */}
                  {prefSkills.map((s) => {
                    const status = statusMap.get(`${cand.candidate}:::${s}`) || 'Missing';
                    const relEntry = cand.related_skills_matched.find(
                      (rel) => rel.toLowerCase().startsWith(s.toLowerCase() + ' (via ') || rel.toLowerCase().includes(s.toLowerCase())
                    );
                    const relParsed = relEntry ? parseRelatedSkillMatch(relEntry) : null;

                    return (
                      <td
                        key={s}
                        className="p-1.5 text-center border-r border-slate-100 dark:border-midnight-border"
                      >
                        <div
                          className={`w-11 h-11 mx-auto rounded-lg flex flex-col items-center justify-center font-bold transition shadow-xs ${
                            status === 'Exact Match'
                              ? 'bg-emerald-100/90 text-emerald-800 border border-emerald-400 dark:bg-midnight-tint/70 dark:border-midnight-ink dark:text-midnight-ink'
                              : status === 'Related Match'
                              ? 'bg-amber-100/90 text-amber-800 border border-amber-400 dark:bg-midnight-secondary/70 dark:border-midnight-hover dark:text-midnight-hover'
                              : 'bg-rose-100/80 text-rose-800 border border-rose-300 dark:bg-midnight-secondary/60 dark:border-midnight-secondary dark:text-midnight-hover'
                          }`}
                          title={
                            status === 'Related Match' && relParsed
                              ? `${cand.candidate} — ${s}: Related match via ${relParsed.sourceSkill} (${relParsed.weightPercent}% credit)`
                              : `${cand.candidate} — ${s}: ${status}`
                          }
                        >
                          <span className="text-base leading-none">
                            {status === 'Exact Match' ? '✓' : status === 'Related Match' ? '≈' : '✗'}
                          </span>
                          {status === 'Related Match' && relParsed && (
                            <span className="text-[8px] font-semibold truncate max-w-[38px] leading-tight mt-0.5">
                              {relParsed.displayLabel}
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}

                  {/* Summary Column */}
                  <td className="p-2.5 text-center bg-slate-50/50 dark:bg-midnight-canvas/30">
                    <div className="font-bold text-accent-600 dark:text-midnight-primary text-xs">
                      {reqMatchedCount}/{reqSkills.length} required ({reqPct}%)
                    </div>
                    {hasPref && (
                      <div className="text-[11px] font-semibold text-purple-600 dark:text-midnight-muted mt-0.5">
                        {prefMatchedCount}/{prefSkills.length} preferred
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Stats Line */}
      <div className="mt-4 pt-3 border-t border-slate-100 dark:border-midnight-border flex items-center justify-between text-xs text-slate-500 dark:text-midnight-muted">
        <span className="flex items-center space-x-1.5 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-accent-500 dark:text-midnight-primary" />
          <span>
            <strong>{rankings.length}</strong> candidate{rankings.length !== 1 ? 's' : ''} × <strong>{allSkills.length}</strong> skills:
          </span>
          <span className="text-emerald-600 dark:text-midnight-ink font-semibold">{totalExact} exact</span>,
          <span className="text-amber-600 dark:text-midnight-hover font-semibold">{totalRelated} related</span>,
          <span className="text-rose-600 dark:text-midnight-hover font-semibold">{totalMissing} missing</span>
        </span>
      </div>
    </div>
  );
};
