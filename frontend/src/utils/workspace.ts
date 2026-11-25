import type { CandidateRanking, HybridWeights, JobOverrides } from '../types/api';

export const DEFAULT_WEIGHTS: HybridWeights = { semantic_weight: 0.4, keyword_weight: 0.2, skill_weight: 0.3, experience_weight: 0.1, anonymize: true };
export const WEIGHTS = [
  ['semantic_weight', 'Semantic similarity'],
  ['keyword_weight', 'Keyword relevance'],
  ['skill_weight', 'Skill match'],
  ['experience_weight', 'Experience relevance'],
] as const;

export const EMPTY_OVERRIDES: JobOverrides = { job_title: '', required_skills: '', preferred_skills: '', min_experience_years: '' };

export const candidateId = (candidate: CandidateRanking) => candidate.candidate_id || candidate.candidate;
