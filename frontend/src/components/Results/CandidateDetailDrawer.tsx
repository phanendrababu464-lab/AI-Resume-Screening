import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Award,
  AlertTriangle,
  CheckCircle2,
  Layers,
  Cpu,
  Clock,
  FileText,
  Sparkles,
  HelpCircle,
  Copy,
  Check,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import type { CandidateRanking, GeminiValidationResponse } from '../../types/api.ts';
import { validateResumeWithGemini } from '../../services/api.ts';
import { formatPercent } from '../../utils/helpers.ts';

interface CandidateDetailDrawerProps {
  candidate: CandidateRanking | null;
  jobText?: string;
  onClose: () => void;
}

export const CandidateDetailDrawer: React.FC<CandidateDetailDrawerProps> = ({
  candidate,
  jobText = '',
  onClose,
}) => {
  const [validation, setValidation] = useState<GeminiValidationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [copiedQuestions, setCopiedQuestions] = useState<boolean>(false);

  const validationRequest = useRef<AbortController | null>(null);

  // Reset the analysis when the selected candidate or job changes.
  useEffect(() => {
    setValidation(null);
    setLoading(false);
    setCopiedQuestions(false);
    return () => {
      validationRequest.current?.abort();
      validationRequest.current = null;
    };
  }, [candidate, jobText]);

  if (!candidate) return null;

  const handleRunValidation = async () => {
    validationRequest.current?.abort();
    const request = new AbortController();
    validationRequest.current = request;
    setLoading(true);
    try {
      const res = await validateResumeWithGemini({
        job_text: jobText || 'Technical Software Engineering Position',
        candidate_name: candidate.candidate,
        candidate_text: candidate.resume_snippet || '',
        matched_skills: candidate.matched_skills,
        missing_skills: candidate.missing_skills,
      }, request.signal);
      if (!request.signal.aborted) setValidation(res);
    } catch (err: unknown) {
      if (request.signal.aborted) return;
      setValidation({
        status: 'error',
        validation_score: null,
        executive_summary: 'Failed to contact Gemini validation service.',
        strengths: [],
        risks_or_concerns: [],
        interview_questions: [],
        authenticity_assessment: '',
        error_message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      if (validationRequest.current === request) {
        validationRequest.current = null;
        setLoading(false);
      }
    }
  };

  const handleCopyQuestions = () => {
    if (!validation?.interview_questions || validation.interview_questions.length === 0) return;
    const text = validation.interview_questions.map((q, idx) => `${idx + 1}. ${q}`).join('\n\n');
    navigator.clipboard.writeText(text);
    setCopiedQuestions(true);
    setTimeout(() => setCopiedQuestions(false), 2000);
  };

  const cs = candidate.component_scores;

  const components = [
    {
      name: 'Required Skill Coverage',
      score: cs.required_skill_score !== null ? cs.required_skill_score * 100 : null,
      icon: CheckCircle2,
      color: 'bg-theme-primary',
    },
    {
      name: 'Preferred Skill Coverage',
      score: cs.preferred_skill_score !== null ? cs.preferred_skill_score * 100 : null,
      icon: Layers,
      color: 'bg-theme-muted',
    },
    {
      name: 'Semantic Similarity',
      score: cs.semantic_score !== null ? cs.semantic_score * 100 : null,
      icon: Cpu,
      color: 'bg-theme-ink',
    },
    {
      name: 'Experience Alignment',
      score: cs.experience_score !== null ? cs.experience_score * 100 : null,
      icon: Clock,
      color: 'bg-theme-hover',
    },
    {
      name: 'TF-IDF Baseline Match',
      score: cs.tfidf_baseline_score !== null && cs.tfidf_baseline_score !== undefined ? cs.tfidf_baseline_score * 100 : null,
      icon: FileText,
      color: 'bg-theme-muted',
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
        className="fixed inset-0 w-screen h-screen bg-theme-canvas/60 backdrop-blur-xs transition-opacity cursor-pointer"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-out drawer container anchored to right */}
      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10 z-10 pointer-events-none">
        <div className="w-screen max-w-lg bg-theme-surface border-l border-theme-border h-full shadow-2xl flex flex-col justify-between overflow-y-auto animate-slide-left pointer-events-auto">
          <div>
            {/* Header */}
            <div className="p-6 border-b border-theme-border flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="min-w-6 h-6 px-1.5 rounded-full bg-theme-subtle text-theme-secondary-text flex items-center justify-center font-bold text-xs font-mono">
                    #{candidate.rank_display || candidate.rank}
                  </span>
                  <span className="text-xs font-semibold text-theme-secondary-text">
                    Candidate Detail Card
                  </span>
                </div>
                <h3 id="drawer-title" className="text-xl font-bold text-theme-ink truncate max-w-sm">
                  {candidate.candidate}
                </h3>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-theme-secondary-text hover:text-theme-hover hover:bg-theme-tint transition"
                aria-label="Close candidate drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Score Ring / Composite Metric Banner */}
              <div className="p-4 rounded-xl bg-theme-canvas border border-theme-border flex items-center justify-between">
                <div>
                  <span className="text-xs uppercase font-bold text-theme-secondary-text">
                    Composite Match Score
                  </span>
                  <div className="text-3xl font-extrabold font-mono text-theme-primary mt-0.5">
                    {formatPercent(candidate.match_score, 1)}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  {candidate.below_min_experience && (
                    <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-theme-secondary/80 text-theme-hover border border-theme-secondary text-xs font-semibold">
                      <AlertTriangle className="w-4 h-4 text-theme-hover" />
                      <span>Below Min Exp</span>
                    </div>
                  )}
                  {candidate.is_duplicate && (
                    <div className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-theme-secondary/80 text-theme-hover border border-theme-secondary text-xs font-semibold">
                      <AlertTriangle className="w-4 h-4 text-theme-hover" />
                      <span>Probable Duplicate</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 5 Component Bars */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-theme-ink uppercase tracking-wider">
                  Evaluation Component Breakdown
                </h4>
                <div className="space-y-2.5">
                  {components.map((comp) => (
                    <div key={comp.name} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="flex items-center space-x-1.5 font-medium text-theme-secondary-text">
                          <comp.icon className="w-3.5 h-3.5 text-theme-secondary-text" />
                          <span>{comp.name}</span>
                        </span>
                        <span className="font-mono font-bold text-theme-ink">
                          {formatPercent(comp.score, 1)}
                        </span>
                      </div>
                      <div className="w-full bg-theme-subtle h-2 rounded-full overflow-hidden">
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
              <h4 className="text-xs font-bold text-theme-ink uppercase tracking-wider">
                Skill Taxonomy Breakdown
              </h4>

              {/* Matched Required Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-theme-ink flex items-center space-x-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Matched Required Skills ({candidate.matched_required_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.matched_required_skills.length > 0 ? (
                    candidate.matched_required_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md border bg-theme-tint/60 text-theme-ink border-theme-border text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-theme-secondary-text italic">None matched</span>
                  )}
                </div>
              </div>

              {/* Matched Preferred Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-theme-secondary-text flex items-center space-x-1">
                  <Layers className="w-3.5 h-3.5" />
                  <span>Matched Preferred Skills ({candidate.matched_preferred_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.matched_preferred_skills.length > 0 ? (
                    candidate.matched_preferred_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md border bg-theme-tint/60 text-theme-secondary-text border-theme-border text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-theme-secondary-text italic">None matched</span>
                  )}
                </div>
              </div>

              {/* Related Skills Matched */}
              {candidate.related_skills_matched.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-xs font-semibold text-theme-hover flex items-center space-x-1">
                    <Award className="w-3.5 h-3.5" />
                    <span>Related Skills Partial Credit ({candidate.related_skills_matched.length})</span>
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {candidate.related_skills_matched.map((r, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded-md border bg-theme-secondary/60 text-theme-hover border-theme-secondary text-xs font-medium"
                      >
                        ≈ {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing Required Skills */}
              <div className="space-y-1.5">
                <span className="text-xs font-semibold text-theme-hover flex items-center space-x-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Missing Required Skills ({candidate.missing_required_skills.length})</span>
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {candidate.missing_required_skills.length > 0 ? (
                    candidate.missing_required_skills.map((s) => (
                      <span
                        key={s}
                        className="px-2 py-0.5 rounded-md border bg-theme-secondary/60 text-theme-hover border-theme-secondary text-xs font-medium"
                      >
                        ✗ {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-theme-ink font-medium">
                      ✓ Possesses all mandatory required skills!
                    </span>
                  )}
                </div>
              </div>

              {/* Gemini AI Candidate Validation & Interview Guide */}
              <div className="pt-4 border-t border-theme-border space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <Sparkles className="w-4 h-4 text-theme-primary" />
                    <h4 className="text-xs font-bold text-theme-ink uppercase tracking-wider">
                      Gemini AI Validation
                    </h4>
                  </div>
                  {validation?.model_used && (
                    <span className="text-[10px] font-semibold font-mono px-2 py-0.5 rounded-full bg-theme-tint/60 text-theme-primary border border-theme-secondary">
                      {validation.model_used}
                    </span>
                  )}
                </div>

                {!validation && !loading && (
                  <div className="p-4 rounded-xl bg-theme-canvas border border-dashed border-theme-border text-center space-y-2">
                    <p className="text-xs text-theme-secondary-text">
                      Validate candidate project credibility, verify technical claims, and generate tailored interview questions.
                    </p>
                    <button
                      onClick={handleRunValidation}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-theme-primary hover:bg-theme-hover text-theme-on-accent rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Validate with Gemini</span>
                    </button>
                  </div>
                )}

                {loading && (
                  <div className="p-4 rounded-xl bg-theme-canvas border border-theme-border flex items-center space-x-3 text-xs text-theme-secondary-text">
                    <RefreshCw className="w-4 h-4 text-theme-primary animate-spin" />
                    <span>Analyzing project depth and generating interview guide...</span>
                  </div>
                )}

                {validation && validation.status === 'unconfigured' && (
                  <div className="p-4 rounded-xl bg-theme-secondary/40 border border-theme-secondary/60 space-y-2">
                    <div className="flex items-start space-x-2">
                      <HelpCircle className="w-4 h-4 text-theme-hover shrink-0 mt-0.5" />
                      <div className="text-xs space-y-1">
                        <p className="font-semibold text-theme-hover">
                          AI Validation Ready
                        </p>
                        <p className="text-theme-hover/80 leading-relaxed">
                          Configure <code className="px-1 py-0.5 bg-theme-secondary/60 rounded text-[11px] font-mono">GEMINI_API_KEY</code> on the Render backend or in your local backend environment to activate deep AI resume verification and customized interview guides.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {validation && validation.status === 'error' && (
                  <div className="p-4 rounded-xl bg-theme-secondary/40 border border-theme-secondary/60 space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-1.5 text-xs font-semibold text-theme-hover">
                        <AlertTriangle className="w-4 h-4 text-theme-hover" />
                        <span>AI Validation Error</span>
                      </div>
                      <button
                        onClick={handleRunValidation}
                        className="text-[11px] text-theme-primary hover:underline flex items-center space-x-1 cursor-pointer"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Retry</span>
                      </button>
                    </div>
                    <p className="text-xs text-theme-hover/90">
                      {validation.error_message || 'Could not complete Gemini validation.'}
                    </p>
                  </div>
                )}

                {validation && validation.status === 'success' && (
                  <div className="space-y-3">
                    {/* Authenticity Rating & Metric */}
                    <div className="p-3.5 rounded-xl bg-theme-tint/30 border border-theme-secondary/60 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <ShieldCheck className="w-5 h-5 text-theme-primary" />
                        <div>
                          <div className="text-[11px] uppercase tracking-wider font-bold text-theme-primary">
                            Authenticity Rating
                          </div>
                          <div className="text-xs text-theme-secondary-text">
                            {validation.authenticity_assessment || 'Verified technical profile'}
                          </div>
                        </div>
                      </div>
                      {validation.validation_score !== null && (
                        <div className="text-2xl font-black font-mono text-theme-primary">
                          {validation.validation_score}<span className="text-xs text-theme-secondary-text">/100</span>
                        </div>
                      )}
                    </div>

                    {/* Executive Summary */}
                    {validation.executive_summary && (
                      <div className="p-3.5 rounded-xl bg-theme-canvas border border-theme-border space-y-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-theme-secondary-text">
                          Executive Fit Summary
                        </span>
                        <p className="text-xs text-theme-secondary-text leading-relaxed">
                          {validation.executive_summary}
                        </p>
                      </div>
                    )}

                    {/* Strengths & Risks */}
                    <div className="grid grid-cols-1 gap-2.5">
                      {validation.strengths.length > 0 && (
                        <div className="p-3 rounded-lg bg-theme-tint/20 border border-theme-border/40 space-y-1.5">
                          <span className="text-[11px] font-bold text-theme-ink flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Validated Strengths</span>
                          </span>
                          <ul className="text-xs text-theme-secondary-text space-y-1 pl-1">
                            {validation.strengths.map((s, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="text-theme-ink font-bold">•</span>
                                <span>{s}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {validation.risks_or_concerns.length > 0 && (
                        <div className="p-3 rounded-lg bg-theme-secondary/20 border border-theme-secondary/40 space-y-1.5">
                          <span className="text-[11px] font-bold text-theme-hover flex items-center space-x-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Validation Risks / Gaps</span>
                          </span>
                          <ul className="text-xs text-theme-secondary-text space-y-1 pl-1">
                            {validation.risks_or_concerns.map((r, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="text-theme-hover font-bold">•</span>
                                <span>{r}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Interview Questions */}
                    {validation.interview_questions.length > 0 && (
                      <div className="p-3.5 rounded-xl bg-theme-tint/20 border border-theme-border/40 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-theme-secondary-text flex items-center space-x-1.5">
                            <HelpCircle className="w-3.5 h-3.5" />
                            <span>Tailored Technical Interview Questions</span>
                          </span>
                          <button
                            onClick={handleCopyQuestions}
                            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium text-theme-secondary-text hover:bg-theme-tint/40 transition cursor-pointer"
                            title="Copy questions to clipboard"
                          >
                            {copiedQuestions ? (
                              <>
                                <Check className="w-3 h-3 text-theme-ink" />
                                <span>Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3 h-3" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                        <ol className="text-xs text-theme-secondary-text space-y-2 list-decimal list-inside pl-0.5">
                          {validation.interview_questions.map((q, i) => (
                            <li key={i} className="leading-relaxed">
                              <span className="font-medium text-theme-ink">{q}</span>
                            </li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-theme-border flex justify-end">
          <button
            onClick={onClose}
            className="w-full py-2.5 bg-theme-primary hover:bg-theme-hover text-theme-on-accent rounded-xl text-xs font-semibold transition"
          >
            Close Detail Drawer
          </button>
        </div>
      </div>
    </div>
  </div>
  );
};
