/**
 * Utility helpers for presentation formatting, file validation, and UI weight normalization.
 * Note: These are UI-only convenience helpers and contain NO scoring or ranking business logic.
 */

import type { Recommendation } from '../types/api.ts';

export interface WeightSet {
  required: number;
  preferred: number;
  semantic: number;
  experience: number;
}

/**
 * Normalizes four scoring weights so that their sum equals exactly 1.00.
 * Reconciles minor hundredth-decimal rounding differences onto the largest component.
 */
export function normalizeWeights(weights: WeightSet): WeightSet {
  const sum = weights.required + weights.preferred + weights.semantic + weights.experience;

  // Fallback if user set all sliders to zero
  if (sum <= 0) {
    return {
      required: 0.50,
      preferred: 0.20,
      semantic: 0.20,
      experience: 0.10,
    };
  }

  // Calculate raw proportional values
  let req = Math.round((weights.required / sum) * 100) / 100;
  let pref = Math.round((weights.preferred / sum) * 100) / 100;
  let sem = Math.round((weights.semantic / sum) * 100) / 100;
  let exp = Math.round((weights.experience / sum) * 100) / 100;

  // Reconcile rounding discrepancies against exactly 1.00
  const currentSum = Math.round((req + pref + sem + exp) * 100) / 100;
  const diff = Math.round((1.00 - currentSum) * 100) / 100;

  if (diff !== 0) {
    // Add discrepancy to largest weight
    if (req >= pref && req >= sem && req >= exp) {
      req = Math.round((req + diff) * 100) / 100;
    } else if (pref >= req && pref >= sem && pref >= exp) {
      pref = Math.round((pref + diff) * 100) / 100;
    } else if (sem >= req && sem >= pref && sem >= exp) {
      sem = Math.round((sem + diff) * 100) / 100;
    } else {
      exp = Math.round((exp + diff) * 100) / 100;
    }
  }

  return {
    required: Math.max(0, req),
    preferred: Math.max(0, pref),
    semantic: Math.max(0, sem),
    experience: Math.max(0, exp),
  };
}

/**
 * Formats a numeric score value into a readable percentage string with half-up rounding.
 * Automatically handles values given in either 0-1 scale or 0-100 scale.
 * Non-applicable (null / undefined) scores display 'N/A'.
 */
export function formatPercent(value: number | null | undefined, decimals: number = 1): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  if (value === 0) {
    return decimals === 0 ? '0%' : `${(0).toFixed(decimals)}%`;
  }

  // If score is given on 0-1 scale (<= 1.0), scale to 100
  const normalized = value <= 1.0 && value > 0 ? value * 100 : value;
  const factor = Math.pow(10, decimals);
  const rounded = Math.round((normalized + Number.EPSILON) * factor) / factor;
  return `${rounded.toFixed(decimals)}%`;
}

/**
 * Formats margin over runner-up in points (e.g., "+4.8 pts").
 */
export function formatPts(value: number | null | undefined, decimals: number = 1): string {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  const factor = Math.pow(10, decimals);
  const rounded = Math.round((value + Number.EPSILON) * factor) / factor;
  const prefix = rounded > 0 ? '+' : '';
  return `${prefix}${rounded.toFixed(decimals)} pts`;
}

/**
 * Constructs the deterministic recommendation hero sentence from structured API numbers
 * using the unified formatPercent and formatPts formatters.
 * Guarantees 100% rounding and formatting consistency with leaderboard and drawer.
 */
export function buildRecommendationSentence(recommendation: Recommendation, decimals: number = 1): string {
  const {
    best_candidate,
    best_score,
    runner_up,
    runner_up_score,
    margin_over_runner_up,
    missing_skills,
    is_tie,
    tied_candidates,
    warnings,
  } = recommendation;

  if (!best_candidate || best_score === null) return '';

  const bestScoreFormatted = formatPercent(best_score, decimals);
  const parts: string[] = [
    `${best_candidate} is the recommended top candidate with a composite score of ${bestScoreFormatted}.`,
  ];

  if (is_tie && tied_candidates && tied_candidates.length > 1) {
    const otherNames = tied_candidates.filter((c) => c !== best_candidate).join(', ');
    parts.push(`Tied for top position with ${otherNames} (${bestScoreFormatted}).`);
  } else if (!runner_up || runner_up_score === null || margin_over_runner_up === null) {
    parts.push(`${best_candidate} was the sole candidate evaluated.`);
  } else {
    const runnerScoreFormatted = formatPercent(runner_up_score, decimals);
    const marginFormatted = formatPts(margin_over_runner_up, decimals);
    if (runner_up.includes('(Tied)')) {
      const runnerNames = runner_up.replace(' (Tied)', '');
      parts.push(`Outperforms tied runners-up ${runnerNames} (${runnerScoreFormatted}) by a margin of ${marginFormatted}.`);
    } else {
      parts.push(`Outperforms runner-up ${runner_up} (${runnerScoreFormatted}) by a margin of ${marginFormatted}.`);
    }
  }

  // Missing skills / partial fit / alignment note
  const hasBelowExpWarning = warnings && warnings.some((w) => w.toLowerCase().includes('below minimum'));
  if (missing_skills && missing_skills.length > 0) {
    parts.push(`Rated as best available match, partial fit (missing required skills: ${missing_skills.join(', ')}).`);
  } else if (hasBelowExpWarning) {
    parts.push(`Rated as best available match, partial fit (falls below the minimum required experience).`);
  } else if (best_score < 50.0) {
    parts.push(`Rated as best available match, partial fit (composite score below 50% (${bestScoreFormatted})).`);
  } else {
    parts.push(`Demonstrates strong alignment with role requirements.`);
  }

  return parts.join(' ');
}

/**
 * Standardizes all embedded percentages and margins within recommendation summary text
 * using the unified formatPercent and formatPts paths.
 */
export function formatRecommendationText(text: string, decimals: number = 1): string {
  if (!text) return '';
  // Normalize margins like "+4.8%" to "+4.8 pts"
  let result = text.replace(/\+(\d+(?:\.\d+)?)\s*%/g, (_, numStr) => {
    return formatPts(parseFloat(numStr), decimals);
  });
  // Normalize any remaining percentages (e.g. 82% -> 82.0%)
  result = result.replace(/(\d+(?:\.\d+)?)\s*%/g, (_, numStr) => {
    return formatPercent(parseFloat(numStr), decimals);
  });
  return result;
}

/**
 * Formats byte count into human-readable file size (KB / MB).
 */
export function formatBytes(bytes: number, decimals: number = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
export const MAX_RESUMES = 100;
export const MAX_RESUME_COUNT = MAX_RESUMES;
export const ALLOWED_EXTENSIONS = ['.pdf', '.docx'];

/**
 * Validates a single resume file for allowed extension and 5 MB size limit.
 */
export function validateResumeFile(file: File): { valid: boolean; error?: string } {
  const name = file.name.toLowerCase();
  const hasValidExt = ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext));

  if (!hasValidExt) {
    return {
      valid: false,
      error: `"${file.name}" has an unsupported format. Only PDF and DOCX files are accepted.`,
    };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: `"${file.name}" (${formatBytes(file.size)}) exceeds the maximum allowed file size of 5 MB.`,
    };
  }

  return { valid: true };
}

/**
 * Validates a collection of files against count limit and per-file validity.
 */
export function validateResumeFileList(
  files: File[],
  maxCount: number = MAX_RESUMES
): { valid: boolean; error?: string } {
  if (files.length === 0) {
    return { valid: false, error: 'Please upload at least one resume.' };
  }

  if (files.length > maxCount) {
    return {
      valid: false,
      error: `Maximum ${maxCount} resumes allowed per screening batch (selected ${files.length}).`,
    };
  }

  for (const f of files) {
    const singleCheck = validateResumeFile(f);
    if (!singleCheck.valid) {
      return singleCheck;
    }
  }

  return { valid: true };
}

/**
 * Extracts related match details from backend strings like "FastAPI (via Express.js: 0.4)".
 */
export function parseRelatedSkillMatch(relText: string): {
  targetSkill: string;
  sourceSkill: string;
  weightPercent: number;
  displayLabel: string;
} {
  const match = relText.match(/^(.*?)\s*\(via\s+([^:]+):\s*([\d.]+)\)/i);
  if (match) {
    const targetSkill = match[1].trim();
    const sourceSkill = match[2].trim();
    const rawWeight = parseFloat(match[3].trim());
    const weightPercent = Math.round(rawWeight * 100);
    return {
      targetSkill,
      sourceSkill,
      weightPercent,
      displayLabel: `${sourceSkill} (${weightPercent}%)`,
    };
  }

  return {
    targetSkill: relText,
    sourceSkill: 'Related',
    weightPercent: 50,
    displayLabel: 'Related',
  };
}
