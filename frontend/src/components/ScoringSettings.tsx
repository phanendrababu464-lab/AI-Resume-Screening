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
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-card transition-colors overflow-hidden">
      {/* Header bar / Toggle */}
      <div className="px-5 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-50/50 dark:bg-slate-900/50">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center space-x-2 text-slate-800 dark:text-slate-100 font-semibold text-sm hover:text-accent-600 dark:hover:text-accent-400 transition"
          aria-expanded={isOpen}
          aria-label="Toggle scoring settings panel"
        >
          <div className="w-7 h-7 rounded-lg bg-accent-50 dark:bg-accent-950/60 text-accent-600 dark:text-accent-400 flex items-center justify-center">
            <Sliders className="w-4 h-4" />
          </div>
          <span>3. Scoring Parameters & Weight Configuration</span>
          {isOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>

        {/* Live Total Badge & Run Action */}
        <div className="flex items-center space-x-3 w-full sm:w-auto justify-between sm:justify-end">
          {/* Live total badge */}
          <div
            className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
              isSumValid
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800'
                : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800'
            }`}
          >
            {isSumValid ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                <span>Total: 100% (Balanced)</span>
              </>
            ) : (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
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
                ? 'bg-accent-600 hover:bg-accent-700 text-white shadow-accent-500/25 cursor-pointer active:scale-98'
                : 'bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed shadow-none'
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
        <div className="px-5 py-2 bg-amber-50/70 dark:bg-amber-950/20 border-t border-amber-200/50 dark:border-amber-900/30 flex items-center space-x-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-amber-500" />
          <span>{disabledReason}</span>
        </div>
      )}

      {/* Collapsible Sliders Content */}
      {isOpen && (
        <div className="p-5 border-t border-slate-200 dark:border-slate-800 space-y-6">
          {/* Weight Sliders */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* 1. Required Skill Weight */}
            <div className="space-y-2 bg-slate-50 dark:bg-slate-950/40 p-3.5 rounded-xl border border-slate-200/60 dark:border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Required Skills</span>
                <span className="font-mono font-bold text-accent-600 dark:text-accent-400 bg-accent-50 dark:bg-accent-950 px-2 py-0.5 rounded">
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
                className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-accent-600"
                aria-label="Required skills weight slider"
              />
              <p className="text-[11px] text-slate-400">Mandatory skill coverage</p>
            </div>

            {/* 2. Preferred Skill Weight */}
            <div className="space-y-2 bg-slate-50 dark:bg-slate-950/40 p-3.5 rounded-xl border border-slate-200/60 dark:border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Preferred Skills</span>
                <span className="font-mono font-bold text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950 px-2 py-0.5 rounded">
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
                className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-purple-600"
                aria-label="Preferred skills weight slider"
              />
              <p className="text-[11px] text-slate-400">Bonus & advantageous skills</p>
            </div>

            {/* 3. Semantic Similarity Weight */}
            <div className="space-y-2 bg-slate-50 dark:bg-slate-950/40 p-3.5 rounded-xl border border-slate-200/60 dark:border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Semantic Match</span>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 px-2 py-0.5 rounded">
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
                className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-emerald-600"
                aria-label="Semantic similarity weight slider"
              />
              <p className="text-[11px] text-slate-400">MiniLM embedding cosine match</p>
            </div>

            {/* 4. Experience Match Weight */}
            <div className="space-y-2 bg-slate-50 dark:bg-slate-950/40 p-3.5 rounded-xl border border-slate-200/60 dark:border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">Experience Match</span>
                <span className="font-mono font-bold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950 px-2 py-0.5 rounded">
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
                className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-600"
                aria-label="Experience match weight slider"
              />
              <p className="text-[11px] text-slate-400">Years alignment vs minimum</p>
            </div>
          </div>

          {/* Action Row: Normalize, Penalty, Anonymize, Reset */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-100 dark:border-slate-800/80">
            {/* Left Controls: Penalty and Anonymize */}
            <div className="flex flex-wrap items-center gap-6">
              {/* Penalty Slider */}
              <div className="flex items-center space-x-3 text-xs">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Experience Penalty Multiplier:
                </span>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={weights.experience_penalty}
                  onChange={(e) => handleSliderChange('experience_penalty', parseFloat(e.target.value))}
                  className="w-28 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-rose-500"
                  aria-label="Below-minimum experience penalty multiplier slider"
                />
                <span className="font-mono font-bold text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded">
                  ×{weights.experience_penalty.toFixed(2)}
                </span>
              </div>

              {/* Anonymize Toggle */}
              <label className="inline-flex items-center space-x-2 text-xs font-semibold text-slate-700 dark:text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={weights.anonymize}
                  onChange={(e) => onWeightsChange({ ...weights, anonymize: e.target.checked })}
                  className="rounded text-accent-600 focus:ring-accent-500 w-4 h-4 cursor-pointer"
                  aria-label="Anonymize candidate PII toggle"
                />
                <ShieldCheck className="w-4 h-4 text-accent-500" />
                <span>Anonymize PII (Names, Emails, Phones)</span>
              </label>
            </div>

            {/* Right Buttons: Normalize & Reset */}
            <div className="flex items-center space-x-2.5">
              <button
                type="button"
                onClick={handleNormalize}
                className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-accent-50 text-accent-700 dark:bg-accent-950/60 dark:text-accent-300 border border-accent-200 dark:border-accent-800 hover:bg-accent-100 transition"
                aria-label="Normalize weights to 100 percent"
              >
                <Scale className="w-3.5 h-3.5" />
                <span>Normalize to 100%</span>
              </button>

              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition"
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
