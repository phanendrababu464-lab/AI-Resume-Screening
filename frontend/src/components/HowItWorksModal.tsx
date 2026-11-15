import React from 'react';
import { X, Calculator, ShieldCheck, CheckCircle2, AlertTriangle, Layers } from 'lucide-react';
import type { ScoringWeights } from '../types/api.ts';

interface HowItWorksModalProps {
  isOpen: boolean;
  onClose: () => void;
  weights: ScoringWeights;
}

export const HowItWorksModal: React.FC<HowItWorksModalProps> = ({ isOpen, onClose, weights }) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="flex items-center space-x-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-accent-100 text-accent-600 dark:bg-accent-950 dark:text-accent-400 flex items-center justify-center">
            <Calculator className="w-5 h-5" />
          </div>
          <div>
            <h2 id="modal-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">
              How Candidate Scoring Works
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Deterministic, explainable, and multi-component ranking methodology
            </p>
          </div>
        </div>

        <div className="space-y-5 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
          {/* Formula */}
          <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800">
            <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-1">
              Composite Match Formula:
            </span>
            <code className="font-mono text-accent-600 dark:text-accent-400 font-bold block text-sm bg-white dark:bg-slate-900 p-2.5 rounded border border-slate-200 dark:border-slate-800 mb-2">
              Score = (w_req × ReqScore + w_pref × PrefScore + w_sem × SemScore + w_exp × ExpScore) × 100
            </code>
            <p className="text-slate-500 dark:text-slate-400 text-[11px]">
              Current active weights: Required ({Math.round(weights.required_skill_weight * 100)}%), Preferred ({Math.round(weights.preferred_skill_weight * 100)}%), Semantic ({Math.round(weights.semantic_weight * 100)}%), Experience ({Math.round(weights.experience_weight * 100)}%).
            </p>
          </div>

          {/* 4 Components */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center space-x-1.5 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-accent-500" />
                <span>1. Required Skills (Coverage)</span>
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Exact matches yield 1.0. Related skills from our IT taxonomy provide partial credit (0.4–0.7).
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center space-x-1.5 mb-1">
                <Layers className="w-3.5 h-3.5 text-purple-500" />
                <span>2. Preferred Skills (Coverage)</span>
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Rewards nice-to-have qualifications and tooling beyond core mandatory requirements.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center space-x-1.5 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span>3. Semantic Similarity</span>
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Cosine similarity between sentence-transformers (all-MiniLM-L6-v2) embeddings of the JD and resume.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
              <span className="font-bold text-slate-800 dark:text-slate-200 flex items-center space-x-1.5 mb-1">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                <span>4. Experience Match</span>
              </span>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">
                Extracted candidate years divided by the job minimum required years, capped at 1.0.
              </p>
            </div>
          </div>

          {/* Experience Gate & Partial Credit */}
          <div className="space-y-3 pt-2">
            <div className="p-3 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-xl">
              <span className="font-semibold text-amber-800 dark:text-amber-300 block mb-0.5">
                ⚠️ Minimum-Experience Gate:
              </span>
              <p className="text-slate-600 dark:text-slate-300 text-[11px]">
                If a candidate's extracted years of experience fall below the job's minimum requirement, their final composite score is multiplied by the penalty factor (current: ×{weights.experience_penalty.toFixed(2)}) and flagged with a warning.
              </p>
            </div>

            <div className="p-3 bg-blue-50/50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900/40 rounded-xl">
              <span className="font-semibold text-blue-800 dark:text-blue-300 block mb-0.5">
                ≈ Related-Skill Partial Credit:
              </span>
              <p className="text-slate-600 dark:text-slate-300 text-[11px]">
                Unmatched skills automatically receive credit if related technologies are present (e.g. MySQL for PostgreSQL yields 0.50 credit; Flask for FastAPI yields 0.60 credit). Exact matches always take precedence and score 1.0.
              </p>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl flex items-start space-x-2">
              <ShieldCheck className="w-4 h-4 text-accent-500 flex-shrink-0 mt-0.5" />
              <p className="text-slate-500 dark:text-slate-400 text-[11px]">
                Demographic invariance: candidate scores remain mathematically invariant whether evaluated in normal or anonymized mode (names, emails, phones, pronouns removed).
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 dark:bg-slate-100 dark:hover:bg-white text-white dark:text-slate-900 rounded-xl text-xs font-semibold transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
