import type {
  HealthResponse,
  SamplesResponse,
  JobAnalyzeResponse,
  ScreenResponse,
  ScoringWeights,
  CandidateRanking,
} from '../types/api.ts';

const BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Checks backend health status.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

/**
 * Fetches sample job descriptions and sample resumes.
 */
export async function fetchSamples(): Promise<SamplesResponse> {
  const res = await fetch(`${BASE_URL}/api/samples`);
  if (!res.ok) {
    throw new Error(`Failed to fetch samples: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Downloads a sample resume from the backend as a browser File object.
 */
export async function fetchSampleResumeFile(filename: string): Promise<File> {
  const res = await fetch(`${BASE_URL}/api/samples/resume/${encodeURIComponent(filename)}`);
  if (!res.ok) {
    throw new Error(`Failed to load sample resume ${filename}`);
  }
  const blob = await res.blob();
  const mediaType = filename.toLowerCase().endsWith('.pdf')
    ? 'application/pdf'
    : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  return new File([blob], filename, { type: mediaType });
}

/**
 * Sends job text to the backend for real-time skill & experience extraction preview.
 */
export async function analyzeJob(text: string): Promise<JobAnalyzeResponse> {
  const res = await fetch(`${BASE_URL}/api/jobs/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    throw new Error(`Job analysis failed: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Uploads job text and resume files to screen candidates with configured weights.
 */
export async function screenResumes(
  jobText: string,
  files: File[],
  weights: ScoringWeights,
  options?: {
    useSampleResumes?: boolean;
    sampleResumeIds?: string[];
  }
): Promise<ScreenResponse> {
  const formData = new FormData();
  formData.append('job_text', jobText);
  formData.append('required_skill_weight', weights.required_skill_weight.toString());
  formData.append('preferred_skill_weight', weights.preferred_skill_weight.toString());
  formData.append('semantic_weight', weights.semantic_weight.toString());
  formData.append('experience_weight', weights.experience_weight.toString());
  formData.append('experience_penalty', weights.experience_penalty.toString());
  formData.append('anonymize', weights.anonymize.toString());

  if (options?.useSampleResumes) {
    formData.append('use_sample_resumes', 'true');
  }
  if (options?.sampleResumeIds && options.sampleResumeIds.length > 0) {
    formData.append('sample_resume_ids', options.sampleResumeIds.join(','));
  }

  // Attach actual uploaded file objects
  for (const file of files) {
    formData.append('files', file);
  }

  const res = await fetch(`${BASE_URL}/api/screen`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = `Screening failed: ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // fallback to statusText
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

/**
 * Downloads candidate ranking results as a formatted CSV spreadsheet.
 */
export async function exportCsv(rankings: CandidateRanking[], jobTitle?: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      job_title: jobTitle || 'Screening Results',
      rankings,
    }),
  });

  if (!res.ok) {
    throw new Error('Failed to export CSV results');
  }

  const blob = await res.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = downloadUrl;
  const sanitizedTitle = (jobTitle || 'screening_results')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_');
  a.download = `${sanitizedTitle}_results.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(downloadUrl);
}
