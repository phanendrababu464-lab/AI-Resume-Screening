import React, { useState } from 'react';
import {
  Sliders,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Scale,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Play,
  Loader2,
} from 'lucide-react';
import type { ScoringWeights } from '../types/api.ts';
import { normalizeWeights } from '../utils/helpers.ts';

interface ScoringSettingsProps {
  weights: ScoringWeights;
  onWeightsChange: (weights: ScoringWeights) => void;
  isValidToRun: boolean;
  disabledReason: string | null;
  isRunning: boolean;
  onRun: () => void;
}

const DEFAULT_WEIGHTS: ScoringWeights = {
  required_skill_weight: 0.50,
  preferred_skill_weight: 0.20,
  semantic_weight: 0.20,
  experience_weight: 0.10,
  experience_penalty: 0.60,
  anonymize: false,
};

export const ScoringSettings: React.FC<ScoringSettingsProps> = ({
  weights,
  onWeightsChange,
  isValidToRun,
  disabledReason,
  isRunning,
  onRun,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const totalSum = Math.round(
    (weights.required_skill_weight +
      weights.preferred_skill_weight +
      weights.semantic_weight +
      weights.experience_weight) *
      100
  ) / 100;

  const isSumValid = Math.abs(totalSum - 1.0) <= 0.005;

  const handleSliderChange = (key: keyof ScoringWeights, val: number) => {
    onWeightsChange({
      ...weights,
      [key]: val,
    });
  };

  const handleNormalize = () => {
    const normalized = normalizeWeights({
      required: weights.required_skill_weight,
      preferred: weights.preferred_skill_weight,
      semantic: weights.semantic_weight,
      experience: weights.experience_weight,
    });

    onWeightsChange({
      ...weights,
      required_skill_weight: normalized.required,
      preferred_skill_weight: normalized.preferred,
      semantic_weight: normalized.semantic,
      experience_weight: normalized.experience,
    });
  };

  const handleReset = () => {
    onWeightsChange({ ...DEFAULT_WEIGHTS });
  };

  return (
    <div className="bg-theme-surface border border-theme-border rounded-2xl shadow-card transition-colors overflow-hidden">
      {/* Header bar / Toggle */}
      <div className="px-5 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-theme-surface/50">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center space-x-2 text-theme-ink font-semibold text-sm hover:text-theme-hover transition"
          aria-expanded={isOpen}
          aria-label="Toggle scoring settings panel"
        >
          <div className="w-7 h-7 rounded-lg bg-theme-tint/60 text-theme-primary flex items-center justify-center">
            <Sliders className="w-4 h-4" />
          </div>
          <span>3. Scoring Parameters & Weight Configuration</span>
          {isOpen ? <ChevronUp className="w-4 h-4 text-theme-secondary-text" /> : <ChevronDown className="w-4 h-4 text-theme-secondary-text" />}
        </button>

        {/* Live Total Badge & Run Action */}
        <div className="flex items-center space-x-3 w-full sm:w-auto justify-between sm:justify-end">
          {/* Live total badge */}
          <div
            className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              isSumValid
                ? 'bg-theme-tint/40 text-theme-ink border-theme-border'
                : 'bg-theme-secondary/40 text-theme-hover border-theme-secondary'
            }`}
          >
            {isSumValid ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-theme-ink" />
                <span>Total: 100% (Balanced)</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-theme-hover" />
                <span>Total: {Math.round(totalSum * 100)}% (Requires 100%)</span>
              </>
            )}
          </div>

          {/* Primary Screening Run Button */}
          <button
            id="run-screening-button"
            onClick={onRun}
            disabled={!isValidToRun || isRunning}
            className={`inline-flex items-center justify-center space-x-2 px-5 py-2 rounded-xl text-sm font-semibold transition shadow-md ${
              isValidToRun && !isRunning
                ? 'bg-theme-primary hover:bg-theme-hover text-theme-on-accent shadow-theme-primary/25 cursor-pointer active:scale-98'
                : 'bg-theme-subtle text-theme-secondary-text cursor-not-allowed shadow-none'
            }`}
            title={disabledReason || 'Run candidate evaluation and ranking'}
            aria-label="Screen and Rank Resumes"
          >
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Screening Resumes...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Screen & Rank Resumes</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Disabled reason banner when button is disabled */}
      {!isValidToRun && disabledReason && (
        <div className="px-5 py-2 bg-theme-secondary/20 border-t border-theme-secondary/30 flex items-center space-x-2 text-xs text-theme-hover">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-theme-hover" />
          <span>{disabledReason}</span>
        </div>
      )}

      {/* Collapsible Sliders Content */}
      {isOpen && (
        <div className="p-5 border-t border-theme-border space-y-6">
          {/* Weight Sliders */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* 1. Required Skill Weight */}
            <div className="space-y-2 bg-theme-canvas/40 p-3.5 rounded-xl border border-theme-border">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-theme-secondary-text">Required Skills</span>
                <span className="font-mono font-bold text-theme-primary bg-theme-tint px-2 py-0.5 rounded">
                  {Math.round(weights.required_skill_weight * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weights.required_skill_weight}
                onChange={(e) => handleSliderChange('required_skill_weight', parseFloat(e.target.value))}
                className="w-full h-1.5 bg-theme-subtle rounded-lg appearance-none cursor-pointer accent-theme-primary"
                aria-label="Required skills weight slider"
              />
              <p className="text-[11px] text-theme-secondary-text">Mandatory skill coverage</p>
            </div>

            {/* 2. Preferred Skill Weight */}
            <div className="space-y-2 bg-theme-canvas/40 p-3.5 rounded-xl border border-theme-border">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-theme-secondary-text">Preferred Skills</span>
                <span className="font-mono font-bold text-theme-secondary-text bg-theme-tint px-2 py-0.5 rounded">
                  {Math.round(weights.preferred_skill_weight * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weights.preferred_skill_weight}
                onChange={(e) => handleSliderChange('preferred_skill_weight', parseFloat(e.target.value))}
                className="w-full h-1.5 bg-theme-subtle rounded-lg appearance-none cursor-pointer accent-theme-muted"
                aria-label="Preferred skills weight slider"
              />
              <p className="text-[11px] text-theme-secondary-text">Bonus & advantageous skills</p>
            </div>

            {/* 3. Semantic Similarity Weight */}
            <div className="space-y-2 bg-theme-canvas/40 p-3.5 rounded-xl border border-theme-border">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-theme-secondary-text">Semantic Match</span>
                <span className="font-mono font-bold text-theme-ink bg-theme-tint px-2 py-0.5 rounded">
                  {Math.round(weights.semantic_weight * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weights.semantic_weight}
                onChange={(e) => handleSliderChange('semantic_weight', parseFloat(e.target.value))}
                className="w-full h-1.5 bg-theme-subtle rounded-lg appearance-none cursor-pointer accent-theme-ink"
                aria-label="Semantic similarity weight slider"
              />
              <p className="text-[11px] text-theme-secondary-text">MiniLM embedding cosine match</p>
            </div>

            {/* 4. Experience Match Weight */}
            <div className="space-y-2 bg-theme-canvas/40 p-3.5 rounded-xl border border-theme-border">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-theme-secondary-text">Experience Match</span>
                <span className="font-mono font-bold text-theme-hover bg-theme-secondary/40 px-2 py-0.5 rounded">
                  {Math.round(weights.experience_weight * 100)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weights.experience_weight}
                onChange={(e) => handleSliderChange('experience_weight', parseFloat(e.target.value))}
                className="w-full h-1.5 bg-theme-subtle rounded-lg appearance-none cursor-pointer accent-theme-hover"
                aria-label="Experience match weight slider"
              />
              <p className="text-[11px] text-theme-secondary-text">Years alignment vs minimum</p>
            </div>
          </div>

          {/* Action Row: Normalize, Penalty, Anonymize, Reset */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-theme-border/80">
            {/* Left Controls: Penalty and Anonymize */}
            <div className="flex flex-wrap items-center gap-6">
              {/* Penalty Slider */}
              <div className="flex items-center space-x-3 text-xs">
                <span className="font-semibold text-theme-secondary-text">
                  Experience Penalty Multiplier:
                </span>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={weights.experience_penalty}
                  onChange={(e) => handleSliderChange('experience_penalty', parseFloat(e.target.value))}
                  className="w-28 h-1.5 bg-theme-subtle rounded-lg appearance-none cursor-pointer accent-theme-hover"
                  aria-label="Below-minimum experience penalty multiplier slider"
                />
                <span className="font-mono font-bold text-theme-hover bg-theme-secondary/60 px-2 py-0.5 rounded">
                  ×{weights.experience_penalty.toFixed(2)}
                </span>
              </div>

              {/* Anonymize Toggle */}
              <label className="inline-flex items-center space-x-2 text-xs font-semibold text-theme-secondary-text cursor-pointer">
                <input
                  type="checkbox"
                  checked={weights.anonymize}
                  onChange={(e) => onWeightsChange({ ...weights, anonymize: e.target.checked })}
                  className="rounded text-theme-primary focus:ring-theme-primary w-4 h-4 cursor-pointer"
                  aria-label="Anonymize candidate PII toggle"
                />
                <ShieldCheck className="w-4 h-4 text-theme-primary" />
                <span>Anonymize PII (Names, Emails, Phones)</span>
              </label>
            </div>

            {/* Right Buttons: Normalize & Reset */}
            <div className="flex items-center space-x-2.5">
              <button
                type="button"
                onClick={handleNormalize}
                className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-theme-tint/60 text-theme-primary border border-theme-secondary hover:bg-theme-tint transition"
                aria-label="Normalize weights to 100 percent"
              >
                <Scale className="w-3.5 h-3.5" />
                <span>Normalize to 100%</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-theme-subtle text-theme-secondary-text hover:bg-theme-tint transition"
                aria-label="Reset weights to default values"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Defaults</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
