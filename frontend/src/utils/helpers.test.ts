import { describe, it, expect } from 'vitest';
import {
  normalizeWeights,
  formatPercent,
  formatPts,
  buildRecommendationSentence,
  formatRecommendationText,
  formatBytes,
  validateResumeFile,
  validateResumeFileList,
  parseRelatedSkillMatch,
} from './helpers.ts';
import type { Recommendation } from '../types/api.ts';

describe('normalizeWeights', () => {
  it('normalizes arbitrary positive weights so sum equals exactly 1.00', () => {
    const input = { required: 0.8, preferred: 0.5, semantic: 0.3, experience: 0.4 };
    const normalized = normalizeWeights(input);

    const sum = Math.round(
      (normalized.required + normalized.preferred + normalized.semantic + normalized.experience) * 100
    ) / 100;

    expect(sum).toBe(1.00);
    expect(normalized.required).toBeGreaterThan(0);
    expect(normalized.preferred).toBeGreaterThan(0);
  });

  it('handles all zero weights by falling back to standard defaults summing to 1.00', () => {
    const input = { required: 0, preferred: 0, semantic: 0, experience: 0 };
    const normalized = normalizeWeights(input);

    expect(normalized.required).toBe(0.50);
    expect(normalized.preferred).toBe(0.20);
    expect(normalized.semantic).toBe(0.20);
    expect(normalized.experience).toBe(0.10);
  });

  it('leaves already normalized weights unchanged', () => {
    const input = { required: 0.50, preferred: 0.20, semantic: 0.20, experience: 0.10 };
    const normalized = normalizeWeights(input);

    expect(normalized).toEqual(input);
  });
});

describe('formatPercent', () => {
  it('formats decimals (0-1 scale) to clean percentage strings', () => {
    expect(formatPercent(0.9334, 1)).toBe('93.3%');
    expect(formatPercent(0.5, 0)).toBe('50%');
  });

  it('formats values already on 0-100 scale', () => {
    expect(formatPercent(93.34, 1)).toBe('93.3%');
    expect(formatPercent(100, 1)).toBe('100.0%');
  });

  it('handles zero cleanly', () => {
    expect(formatPercent(0, 0)).toBe('0%');
    expect(formatPercent(0, 1)).toBe('0.0%');
  });

  it('handles non-applicable (null / undefined) as N/A', () => {
    expect(formatPercent(null)).toBe('N/A');
    expect(formatPercent(undefined)).toBe('N/A');
  });

  it('rounds half-up consistently when value lands exactly on x.x5', () => {
    // Tests half-up rounding where standard JS toFixed can round down
    expect(formatPercent(82.35, 1)).toBe('82.4%');
    expect(formatPercent(12.25, 1)).toBe('12.3%');
    expect(formatPercent(1.45, 1)).toBe('1.5%');
    expect(formatPercent(0.8235, 1)).toBe('82.4%');
  });
});

describe('formatPts', () => {
  it('formats margin points with a leading plus sign', () => {
    expect(formatPts(4.8)).toBe('+4.8 pts');
    expect(formatPts(0)).toBe('0.0 pts');
    expect(formatPts(null)).toBe('N/A');
  });

  it('rounds half-up on x.x5 values for margin points', () => {
    expect(formatPts(4.85)).toBe('+4.9 pts');
    expect(formatPts(1.25)).toBe('+1.3 pts');
  });
});

describe('buildRecommendationSentence', () => {
  it('builds sentence from structured recommendation numbers matching leaderboard formatting', () => {
    const rec: Recommendation = {
      best_candidate: 'Alice.pdf',
      best_score: 82.35,
      runner_up: 'Bob.docx',
      runner_up_score: 77.55,
      margin_over_runner_up: 4.8,
      missing_skills: ['Docker'],
      strengths: ['Python', 'FastAPI'],
      gaps: ['Docker'],
      warnings: [],
      summary_text: '',
    };

    const sentence = buildRecommendationSentence(rec);
    expect(sentence).toContain('Alice.pdf is the recommended top candidate with a composite score of 82.4%.');
    expect(sentence).toContain('Outperforms runner-up Bob.docx (77.6%) by a margin of +4.8 pts.');
    expect(sentence).toContain('Rated as best available match, partial fit (missing required skills: Docker).');
  });

  it('handles tied winners without naming arbitrary runner-up', () => {
    const rec: Recommendation = {
      best_candidate: 'Candidate A',
      best_score: 73.45,
      runner_up: null,
      runner_up_score: null,
      margin_over_runner_up: 0.0,
      missing_skills: [],
      is_tie: true,
      tied_candidates: ['Candidate A', 'Candidate B'],
      strengths: [],
      gaps: [],
      warnings: [],
      summary_text: '',
    };

    const sentence = buildRecommendationSentence(rec);
    expect(sentence).toContain('Tied for top position with Candidate B (73.5%).');
    expect(sentence).not.toContain('runner-up');
  });

  it('guarantees hero sentence and leaderboard never show different roundings for identical values', () => {
    const testCases = [
      { score: 73.45, expected: '73.5%' },
      { score: 66.05, expected: '66.1%' },
      { score: 50.15, expected: '50.2%' },
      { score: 82.35, expected: '82.4%' },
      { score: 12.05, expected: '12.1%' },
      { score: 99.95, expected: '100.0%' },
    ];

    testCases.forEach(({ score, expected }) => {
      // Leaderboard formatting
      const leaderboardFormatted = formatPercent(score, 1);
      expect(leaderboardFormatted).toBe(expected);

      // Hero sentence formatting
      const rec: Recommendation = {
        best_candidate: 'Winner',
        best_score: score,
        runner_up: 'RunnerUp',
        runner_up_score: 50.0,
        margin_over_runner_up: score - 50.0,
        missing_skills: [],
        strengths: [],
        gaps: [],
        warnings: [],
        summary_text: '',
      };
      const heroSentence = buildRecommendationSentence(rec);
      expect(heroSentence).toContain(leaderboardFormatted);
    });
  });
});

describe('formatRecommendationText', () => {
  it('normalizes embedded percentages and margins to match frontend formatting', () => {
    const text = 'Top candidate Alice with match score of 82.35%. Outperformed runner-up Jane.pdf (78%) by +4.8%.';
    const formatted = formatRecommendationText(text);
    expect(formatted).toContain('82.4%');
    expect(formatted).toContain('78.0%');
    expect(formatted).toContain('+4.8 pts');
  });
});

describe('formatBytes', () => {
  it('formats bytes into KB and MB correctly', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1 KB');
    expect(formatBytes(2.5 * 1024 * 1024)).toBe('2.5 MB');
  });
});

describe('validateResumeFile', () => {
  it('accepts valid PDF files under 5 MB', () => {
    const file = new File(['mock content'], 'alex_mercer.pdf', { type: 'application/pdf' });
    const result = validateResumeFile(file);
    expect(result.valid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it('accepts valid DOCX files under 5 MB', () => {
    const file = new File(['mock content'], 'elena_rostova.docx', {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    const result = validateResumeFile(file);
    expect(result.valid).toBe(true);
  });

  it('rejects unsupported extensions', () => {
    const file = new File(['mock content'], 'script.py', { type: 'text/plain' });
    const result = validateResumeFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('unsupported format');
  });

  it('rejects files exceeding 5 MB', () => {
    // 6 MB mock file
    const largeBlob = new Uint8Array(6 * 1024 * 1024);
    const file = new File([largeBlob], 'giant_resume.pdf', { type: 'application/pdf' });
    const result = validateResumeFile(file);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('exceeds the maximum allowed file size of 5 MB');
  });
});

describe('validateResumeFileList', () => {
  it('rejects empty list', () => {
    const result = validateResumeFileList([]);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Please upload at least one resume');
  });

  it('accepts batches with up to 100 files including 20 files', () => {
    const files20 = Array.from(
      { length: 20 },
      (_, i) => new File(['text'], `resume_${i}.pdf`, { type: 'application/pdf' })
    );
    expect(validateResumeFileList(files20).valid).toBe(true);

    const files100 = Array.from(
      { length: 100 },
      (_, i) => new File(['text'], `resume_${i}.pdf`, { type: 'application/pdf' })
    );
    expect(validateResumeFileList(files100).valid).toBe(true);
  });

  it('rejects batches exceeding 100 files (e.g. 101 files)', () => {
    const files = Array.from(
      { length: 101 },
      (_, i) => new File(['text'], `resume_${i}.pdf`, { type: 'application/pdf' })
    );
    const result = validateResumeFileList(files);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('Maximum 100 resumes allowed');
  });
});

describe('parseRelatedSkillMatch', () => {
  it('parses structured related match strings', () => {
    const parsed = parseRelatedSkillMatch('FastAPI (via Express.js: 0.4)');
    expect(parsed.targetSkill).toBe('FastAPI');
    expect(parsed.sourceSkill).toBe('Express.js');
    expect(parsed.weightPercent).toBe(40);
    expect(parsed.displayLabel).toBe('Express.js (40%)');
  });

  it('handles MySQL to PostgreSQL mapping string', () => {
    const parsed = parseRelatedSkillMatch('PostgreSQL (via MySQL: 0.5)');
    expect(parsed.targetSkill).toBe('PostgreSQL');
    expect(parsed.sourceSkill).toBe('MySQL');
    expect(parsed.weightPercent).toBe(50);
  });
});
