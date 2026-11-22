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

              {/* Gemini AI Candidate Validation & Interview Guide */}
              <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-1.5">
                    <Sparkles className="w-4 h-4 text-accent-500" />
                    <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                      Gemini AI Validation
                    </h4>
                  </div>
                  {validation?.model_used && (
                    <span className="text-[10px] font-semibold font-mono px-2 py-0.5 rounded-full bg-accent-50 dark:bg-accent-950/60 text-accent-700 dark:text-accent-300 border border-accent-200 dark:border-accent-800">
                      {validation.model_used}
                    </span>
                  )}
                </div>

                {!validation && !loading && (
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-dashed border-slate-300 dark:border-slate-800 text-center space-y-2">
                    <p className="text-xs text-slate-600 dark:text-slate-400">
                      Validate candidate project credibility, verify technical claims, and generate tailored interview questions.
                    </p>
                    <button
                      onClick={handleRunValidation}
                      className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-accent-600 hover:bg-accent-700 text-white rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer"
                    >
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Validate with Gemini</span>
                    </button>
                  </div>
                )}

                {loading && (
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 flex items-center space-x-3 text-xs text-slate-600 dark:text-slate-400">
                    <RefreshCw className="w-4 h-4 text-accent-500 animate-spin" />
                    <span>Analyzing project depth and generating interview guide...</span>
                  </div>
                )}

                {validation && validation.status === 'unconfigured' && (
                  <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 space-y-2">
                    <div className="flex items-start space-x-2">
                      <HelpCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      <div className="text-xs space-y-1">
                        <p className="font-semibold text-amber-900 dark:text-amber-200">
                          AI Validation Ready
                        </p>
                        <p className="text-amber-800/90 dark:text-amber-300/80 leading-relaxed">
                          Configure <code className="px-1 py-0.5 bg-amber-100 dark:bg-amber-900/60 rounded text-[11px] font-mono">GEMINI_API_KEY</code> on the Render backend or in your local backend environment to activate deep AI resume verification and customized interview guides.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {validation && validation.status === 'error' && (
                  <div className="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-1.5 text-xs font-semibold text-rose-800 dark:text-rose-300">
                        <AlertTriangle className="w-4 h-4 text-rose-500" />
                        <span>AI Validation Error</span>
                      </div>
                      <button
                        onClick={handleRunValidation}
                        className="text-[11px] text-accent-600 dark:text-accent-400 hover:underline flex items-center space-x-1 cursor-pointer"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>Retry</span>
                      </button>
                    </div>
                    <p className="text-xs text-rose-700 dark:text-rose-300/90">
                      {validation.error_message || 'Could not complete Gemini validation.'}
                    </p>
                  </div>
                )}

                {validation && validation.status === 'success' && (
                  <div className="space-y-3">
                    {/* Authenticity Rating & Metric */}
                    <div className="p-3.5 rounded-xl bg-accent-50/60 dark:bg-accent-950/30 border border-accent-200/80 dark:border-accent-800/60 flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <ShieldCheck className="w-5 h-5 text-accent-600 dark:text-accent-400" />
                        <div>
                          <div className="text-[11px] uppercase tracking-wider font-bold text-accent-800 dark:text-accent-300">
                            Authenticity Rating
                          </div>
                          <div className="text-xs text-slate-600 dark:text-slate-400">
                            {validation.authenticity_assessment || 'Verified technical profile'}
                          </div>
                        </div>
                      </div>
                      {validation.validation_score !== null && (
                        <div className="text-2xl font-black font-mono text-accent-600 dark:text-accent-400">
                          {validation.validation_score}<span className="text-xs text-slate-400">/100</span>
                        </div>
                      )}
                    </div>

                    {/* Executive Summary */}
                    {validation.executive_summary && (
                      <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          Executive Fit Summary
                        </span>
                        <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                          {validation.executive_summary}
                        </p>
                      </div>
                    )}

                    {/* Strengths & Risks */}
                    <div className="grid grid-cols-1 gap-2.5">
                      {validation.strengths.length > 0 && (
                        <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-800/40 space-y-1.5">
                          <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300 flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Validated Strengths</span>
                          </span>
                          <ul className="text-xs text-slate-700 dark:text-slate-300 space-y-1 pl-1">
                            {validation.strengths.map((s, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="text-emerald-500 font-bold">•</span>
                                <span>{s}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {validation.risks_or_concerns.length > 0 && (
                        <div className="p-3 rounded-lg bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200/60 dark:border-rose-800/40 space-y-1.5">
                          <span className="text-[11px] font-bold text-rose-700 dark:text-rose-300 flex items-center space-x-1">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            <span>Validation Risks / Gaps</span>
                          </span>
                          <ul className="text-xs text-slate-700 dark:text-slate-300 space-y-1 pl-1">
                            {validation.risks_or_concerns.map((r, i) => (
                              <li key={i} className="flex items-start space-x-1.5">
                                <span className="text-rose-500 font-bold">•</span>
                                <span>{r}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    {/* Interview Questions */}
                    {validation.interview_questions.length > 0 && (
                      <div className="p-3.5 rounded-xl bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200/60 dark:border-purple-800/40 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700 dark:text-purple-300 flex items-center space-x-1.5">
                            <HelpCircle className="w-3.5 h-3.5" />
                            <span>Tailored Technical Interview Questions</span>
                          </span>
                          <button
                            onClick={handleCopyQuestions}
                            className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-medium text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/40 transition cursor-pointer"
                            title="Copy questions to clipboard"
                          >
                            {copiedQuestions ? (
                              <>
                                <Check className="w-3 h-3 text-emerald-500" />
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
                        <ol className="text-xs text-slate-700 dark:text-slate-300 space-y-2 list-decimal list-inside pl-0.5">
                          {validation.interview_questions.map((q, i) => (
                            <li key={i} className="leading-relaxed">
                              <span className="font-medium text-slate-900 dark:text-slate-100">{q}</span>
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
