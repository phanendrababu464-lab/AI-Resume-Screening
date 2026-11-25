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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-theme-canvas/60 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="bg-theme-surface border border-theme-border rounded-2xl max-w-2xl w-full p-6 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-1 rounded-lg text-theme-secondary-text hover:text-theme-hover transition"
          aria-label="Close modal"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="flex items-center space-x-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-theme-tint text-theme-primary flex items-center justify-center">
            <Calculator className="w-5 h-5" />
          </div>
          <div>
            <h2 id="modal-title" className="text-lg font-bold text-theme-ink">
              How Candidate Scoring Works
            </h2>
            <p className="text-xs text-theme-secondary-text">
              Deterministic, explainable, and multi-component ranking methodology
            </p>
          </div>
        </div>

        <div className="space-y-5 text-xs text-theme-secondary-text leading-relaxed">
          {/* Formula */}
          <div className="bg-theme-canvas p-4 rounded-xl border border-theme-border">
            <span className="font-semibold text-theme-ink block mb-1">
              Composite Match Formula:
            </span>
            <code className="font-mono text-theme-primary font-bold block text-sm bg-theme-surface p-2.5 rounded border border-theme-border mb-2">
              Score = (w_req × ReqScore + w_pref × PrefScore + w_sem × SemScore + w_exp × ExpScore) × 100
            </code>
            <p className="text-theme-secondary-text text-[11px]">
              Current active weights: Required ({Math.round(weights.required_skill_weight * 100)}%), Preferred ({Math.round(weights.preferred_skill_weight * 100)}%), Semantic ({Math.round(weights.semantic_weight * 100)}%), Experience ({Math.round(weights.experience_weight * 100)}%).
            </p>
          </div>

          {/* 4 Components */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg border border-theme-border bg-theme-surface">
              <span className="font-bold text-theme-ink flex items-center space-x-1.5 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-theme-primary" />
                <span>1. Required Skills (Coverage)</span>
              </span>
              <p className="text-[11px] text-theme-secondary-text">
                Exact matches yield 1.0. Related skills from our IT taxonomy provide partial credit (0.4–0.7).
              </p>
            </div>

            <div className="p-3 rounded-lg border border-theme-border bg-theme-surface">
              <span className="font-bold text-theme-ink flex items-center space-x-1.5 mb-1">
                <Layers className="w-3.5 h-3.5 text-theme-secondary-text" />
                <span>2. Preferred Skills (Coverage)</span>
              </span>
              <p className="text-[11px] text-theme-secondary-text">
                Rewards nice-to-have qualifications and tooling beyond core mandatory requirements.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-theme-border bg-theme-surface">
              <span className="font-bold text-theme-ink flex items-center space-x-1.5 mb-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-theme-ink" />
                <span>3. Semantic Similarity</span>
              </span>
              <p className="text-[11px] text-theme-secondary-text">
                Cosine similarity between sentence-transformers (all-MiniLM-L6-v2) embeddings of the JD and resume.
              </p>
            </div>

            <div className="p-3 rounded-lg border border-theme-border bg-theme-surface">
              <span className="font-bold text-theme-ink flex items-center space-x-1.5 mb-1">
                <AlertTriangle className="w-3.5 h-3.5 text-theme-hover" />
                <span>4. Experience Match</span>
              </span>
              <p className="text-[11px] text-theme-secondary-text">
                Extracted candidate years divided by the job minimum required years, capped at 1.0.
              </p>
            </div>
          </div>

          {/* Experience Gate & Partial Credit */}
          <div className="space-y-3 pt-2">
            <div className="p-3 bg-theme-secondary/20 border border-theme-secondary/40 rounded-xl">
              <span className="font-semibold text-theme-hover block mb-0.5">
                ⚠️ Minimum-Experience Gate:
              </span>
              <p className="text-theme-secondary-text text-[11px]">
                If a candidate's extracted years of experience fall below the job's minimum requirement, their final composite score is multiplied by the penalty factor (current: ×{weights.experience_penalty.toFixed(2)}) and flagged with a warning.
              </p>
            </div>

            <div className="p-3 bg-theme-tint/20 border border-theme-border/40 rounded-xl">
              <span className="font-semibold text-theme-primary block mb-0.5">
                ≈ Related-Skill Partial Credit:
              </span>
              <p className="text-theme-secondary-text text-[11px]">
                Unmatched skills automatically receive credit if related technologies are present (e.g. MySQL for PostgreSQL yields 0.50 credit; Flask for FastAPI yields 0.60 credit). Exact matches always take precedence and score 1.0.
              </p>
            </div>

            <div className="p-3 bg-theme-canvas border border-theme-border rounded-xl flex items-start space-x-2">
              <ShieldCheck className="w-4 h-4 text-theme-primary flex-shrink-0 mt-0.5" />
              <p className="text-theme-secondary-text text-[11px]">
                Demographic invariance: candidate scores remain mathematically invariant whether evaluated in normal or anonymized mode (names, emails, phones, pronouns removed).
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-theme-border flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-theme-primary hover:bg-theme-hover text-theme-on-accent rounded-xl text-xs font-semibold transition"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
};
