/**
 * TypeScript definitions mirroring backend Pydantic schemas and API contracts.
 */

export interface JobAnalysis {
  job_title?: string;
  raw_text: string;
  cleaned_text?: string;
  required_skills: string[];
  preferred_skills: string[];
  all_skills: string[];
  min_experience_years?: number | null;
  has_multiple_jobs?: boolean;
  multiple_jobs_warning?: string | null;
}

export interface ComponentScores {
  required_skill_score: number | null;
  preferred_skill_score: number | null;
  semantic_score: number;
  experience_score: number | null;
  tfidf_baseline_score?: number | null;
}

export interface CandidateRanking {
  rank: number;
  rank_display?: string;
  candidate: string;
  match_score: number;
  component_scores: ComponentScores;
  matched_skills: string[];
  missing_skills: string[];
  matched_required_skills: string[];
  matched_preferred_skills: string[];
  missing_required_skills: string[];
  related_skills_matched: string[];
  below_min_experience: boolean;
  is_duplicate?: boolean;
  duplicate_of?: string | null;
  text_hash?: string;
  resume_snippet?: string;
}

export interface GeminiValidationResponse {
  status: 'success' | 'unconfigured' | 'error';
  validation_score: number | null;
  executive_summary: string;
  strengths: string[];
  risks_or_concerns: string[];
  interview_questions: string[];
  authenticity_assessment: string;
  model_used?: string | null;
  error_message?: string | null;
}

export interface ValidateResumeRequest {
  job_text: string;
  candidate_name: string;
  candidate_text?: string;
  matched_skills?: string[];
  missing_skills?: string[];
}

export interface Recommendation {
  best_candidate: string | null;
  best_score: number | null;
  runner_up: string | null;
  runner_up_score: number | null;
  margin_over_runner_up: number | null;
  missing_skills: string[];
  is_tie?: boolean;
  tied_candidates?: string[];
  strengths: string[];
  gaps: string[];
  warnings: string[];
  summary_text: string;
}

export interface OverallChartItem {
  candidate: string;
  score: number;
  label: string;
  rank: number;
  color_category: string;
}

export interface ScoreCompositionItem {
  candidate: string;
  component: string;
  contribution: number;
  percentage_label: string;
  below_min_experience: boolean;
  penalty_note: string;
}

export interface SkillMatrixItem {
  candidate: string;
  skill: string;
  skill_type: 'Required' | 'Preferred';
  skill_display: string;
  status: 'Exact Match' | 'Related Match' | 'Missing';
}

export interface CandidateBreakdownItem {
  component: string;
  percentage: number;
}

export interface ScreenCharts {
  overall: OverallChartItem[];
  composition: ScoreCompositionItem[];
  matrix: SkillMatrixItem[];
  breakdowns: Record<string, CandidateBreakdownItem[]>;
}

export interface FileErrorItem {
  filename: string;
  error: string;
}

export interface ScreenResponse {
  job: JobAnalysis;
  rankings: CandidateRanking[];
  recommendation: Recommendation;
  charts: ScreenCharts;
  total_candidates: number;
  file_errors: FileErrorItem[];
  effective_weights?: Record<string, number>;
  non_applicable_components?: string[];
  weight_redistribution_note?: string | null;
}

export interface HealthResponse {
  status: string;
  version: string;
  service: string;
}

export interface SampleJobItem {
  id: string;
  title: string;
  filename: string;
  text: string;
}

export interface SampleResumeItem {
  id: string;
  filename: string;
  size: number;
}

export interface SamplesResponse {
  jobs: SampleJobItem[];
  resumes: SampleResumeItem[];
}

export interface JobAnalyzeResponse {
  job_title?: string | null;
  required_skills: string[];
  preferred_skills: string[];
  all_skills: string[];
  min_experience_years?: number | null;
  has_multiple_jobs?: boolean;
  multiple_jobs_warning?: string | null;
}

export interface ScoringWeights {
  required_skill_weight: number;
  preferred_skill_weight: number;
  semantic_weight: number;
  experience_weight: number;
  experience_penalty: number;
  anonymize: boolean;
}
