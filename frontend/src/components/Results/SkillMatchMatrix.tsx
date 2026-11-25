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
      <div className="bg-theme-surface border border-theme-border rounded-2xl p-6 text-center text-xs text-theme-secondary-text">
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
    <div className="bg-theme-surface border border-theme-border rounded-2xl p-6 shadow-card transition-colors">
      {/* Header & Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-theme-border/80 mb-4 gap-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-theme-tint/60 text-theme-primary flex items-center justify-center">
            <Target className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-theme-ink uppercase tracking-wider">
              Skill Match Matrix
            </h3>
            <p className="text-xs text-theme-secondary-text">
              Candidate skills matched against job taxonomy requirements
            </p>
          </div>
        </div>

        {/* Compact Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs">
          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded border bg-theme-tint border-theme-ink text-theme-ink flex items-center justify-center font-bold text-xs">
              ✓
            </span>
            <span className="text-theme-secondary-text font-medium">Exact Match (1.0)</span>
          </span>

          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded border bg-theme-secondary/40 border-theme-hover text-theme-hover flex items-center justify-center font-bold text-xs">
              ≈
            </span>
            <span className="text-theme-secondary-text font-medium">Related Match (Partial)</span>
          </span>

          <span className="inline-flex items-center space-x-1.5">
            <span className="w-5 h-5 rounded border bg-theme-secondary/40 border-theme-hover text-theme-hover flex items-center justify-center font-bold text-xs">
              ✗
            </span>
            <span className="text-theme-secondary-text font-medium">Missing (0.0)</span>
          </span>
        </div>
      </div>

      {/* Responsive Horizontal Scroll Wrapper */}
      <div className="w-full overflow-x-auto rounded-xl border border-theme-border bg-theme-surface shadow-sm">
        <table className="w-max min-w-full border-collapse text-xs select-none">
          <thead>
            {/* Tier 1: Group Headers */}
            <tr className="border-b border-theme-border">
              <th
                rowSpan={2}
                className="sticky left-0 z-20 bg-theme-canvas p-3.5 text-left font-bold text-theme-ink border-r-2 border-theme-border w-44 min-w-[170px]"
              >
                Candidate
              </th>
              {reqSkills.length > 0 && (
                <th
                  colSpan={reqSkills.length}
                  className={`bg-theme-tint/40 text-theme-primary font-bold uppercase tracking-wider py-2 text-center text-[11px] ${
                    hasPref ? 'border-r-2 border-theme-border' : ''
                  }`}
                >
                  REQUIRED SKILLS ({reqSkills.length})
                </th>
              )}
              {hasPref && (
                <th
                  colSpan={prefSkills.length}
                  className="bg-theme-tint/40 text-theme-secondary-text font-bold uppercase tracking-wider py-2 text-center text-[11px]"
                >
                  PREFERRED SKILLS ({prefSkills.length})
                </th>
              )}
              <th
                rowSpan={2}
                className="bg-theme-canvas p-3 text-center font-bold text-theme-ink w-36 min-w-[130px]"
              >
                Match Summary
              </th>
            </tr>

            {/* Tier 2: Skill Names */}
            <tr className="border-b-2 border-theme-border bg-theme-canvas/50">
              {reqSkills.map((s, idx) => {
                const isLastReq = idx === reqSkills.length - 1 && hasPref;
                return (
                  <th
                    key={s}
                    title={s}
                    className={`p-2 text-center font-semibold text-theme-secondary-text w-20 min-w-[70px] max-w-[80px] break-words leading-tight ${
                      isLastReq ? 'border-r-2 border-theme-border' : 'border-r border-theme-border'
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
                  className="p-2 text-center font-semibold text-theme-secondary-text w-20 min-w-[70px] max-w-[80px] break-words leading-tight border-r border-theme-border"
                >
                  <div className="line-clamp-2 text-[11px]">{s}</div>
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-theme-border/80">
            {rankings.map((cand) => {
              // Find related match info
              const reqMatchedCount = reqSkills.filter((s) => cand.matched_required_skills.includes(s)).length;
              const reqPct = reqSkills.length > 0 ? Math.round((reqMatchedCount / reqSkills.length) * 100) : 0;
              const prefMatchedCount = prefSkills.filter((s) => cand.matched_preferred_skills.includes(s)).length;

              return (
                <tr
                  key={cand.candidate}
                  className="hover:bg-theme-tint/40 transition-colors h-[52px]"
                >
                  {/* Sticky Candidate Name */}
                  <td
                    className="sticky left-0 z-10 bg-theme-surface px-3.5 py-2 font-semibold text-theme-ink border-r-2 border-theme-border truncate max-w-[170px]"
                    title={cand.candidate}
                  >
                    <div className="flex items-center space-x-1.5">
                      <span className="text-[10px] text-theme-secondary-text font-mono font-bold">#{cand.rank}</span>
                      <button
                        onClick={() => onSelectCandidate && onSelectCandidate(cand.candidate)}
                        className="truncate text-left hover:text-theme-hover transition"
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
                          isLastReq ? 'border-r-2 border-theme-border' : 'border-r border-theme-border'
                        }`}
                      >
                        <div
                          className={`w-11 h-11 mx-auto rounded-lg flex flex-col items-center justify-center font-bold transition shadow-xs ${
                            status === 'Exact Match'
                              ? 'border bg-theme-tint/70 border-theme-ink text-theme-ink'
                              : status === 'Related Match'
                              ? 'border bg-theme-secondary/70 border-theme-hover text-theme-hover'
                              : 'border bg-theme-secondary/60 border-theme-secondary text-theme-hover'
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
                        className="p-1.5 text-center border-r border-theme-border"
                      >
                        <div
                          className={`w-11 h-11 mx-auto rounded-lg flex flex-col items-center justify-center font-bold transition shadow-xs ${
                            status === 'Exact Match'
                              ? 'border bg-theme-tint/70 border-theme-ink text-theme-ink'
                              : status === 'Related Match'
                              ? 'border bg-theme-secondary/70 border-theme-hover text-theme-hover'
                              : 'border bg-theme-secondary/60 border-theme-secondary text-theme-hover'
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
                  <td className="p-2.5 text-center bg-theme-canvas/30">
                    <div className="font-bold text-theme-primary text-xs">
                      {reqMatchedCount}/{reqSkills.length} required ({reqPct}%)
                    </div>
                    {hasPref && (
                      <div className="text-[11px] font-semibold text-theme-secondary-text mt-0.5">
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
      <div className="mt-4 pt-3 border-t border-theme-border flex items-center justify-between text-xs text-theme-secondary-text">
        <span className="flex items-center space-x-1.5 font-medium">
          <Sparkles className="w-3.5 h-3.5 text-theme-primary" />
          <span>
            <strong>{rankings.length}</strong> candidate{rankings.length !== 1 ? 's' : ''} × <strong>{allSkills.length}</strong> skills:
          </span>
          <span className="text-theme-ink font-semibold">{totalExact} exact</span>,
          <span className="text-theme-hover font-semibold">{totalRelated} related</span>,
          <span className="text-theme-hover font-semibold">{totalMissing} missing</span>
        </span>
      </div>
    </div>
  );
};
