import type {
  HealthResponse,
  SamplesResponse,
  JobAnalyzeResponse,
  ScreenResponse,
  ScoringWeights,
  CandidateRanking,
  GeminiValidationResponse,
  ValidateResumeRequest,
} from '../types/api.ts';

const RAW_URL = (
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_BASE_URL ||
  ''
).trim();
const BASE_URL = RAW_URL.replace(/\/+$/, '');

/**
 * Builds a properly formatted API endpoint URL, preventing duplicate slashes.
 */
export function getApiUrl(path: string): string {
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return BASE_URL ? `${BASE_URL}${cleanPath}` : cleanPath;
}

/**
 * Executes a fetch request with a configurable timeout and friendly network error messages.
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = 30000
): Promise<Response> {
  if (options.signal?.aborted) throw new Error('Request was cancelled');

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  const cancelRequest = () => controller.abort();
  options.signal?.addEventListener('abort', cancelRequest);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return res;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (options.signal?.aborted) {
        throw new Error('Request was cancelled');
      }
      throw new Error(
        `Backend request timed out after ${Math.round(timeoutMs / 1000)}s. ` +
        `If using Render free tier, the backend may be waking up from sleep (cold start). Please retry in a few moments.`
      );
    }
    if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
      throw new Error(
        `Network error: Unable to reach backend at ${getApiUrl('') || 'server'}. ` +
        `Check your network connection and verify the backend is active.`
      );
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener('abort', cancelRequest);
  }
}

/**
 * Checks backend health status with an 8-second timeout to avoid browser socket exhaustion.
 */
export async function checkHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetchWithTimeout(getApiUrl('/api/health'), { signal }, 8000);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

/**
 * Fetches sample job descriptions and sample resumes.
 */
export async function fetchSamples(signal?: AbortSignal): Promise<SamplesResponse> {
  const res = await fetchWithTimeout(getApiUrl('/api/samples'), { signal }, 25000);
  if (!res.ok) {
    throw new Error(`Failed to fetch samples: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Downloads a sample resume from the backend as a browser File object.
 */
export async function fetchSampleResumeFile(filename: string, signal?: AbortSignal): Promise<File> {
  const res = await fetchWithTimeout(
    getApiUrl(`/api/samples/resume/${encodeURIComponent(filename)}`),
    { signal },
    30000
  );
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
export async function analyzeJob(text: string, signal?: AbortSignal): Promise<JobAnalyzeResponse> {
  const res = await fetchWithTimeout(
    getApiUrl('/api/jobs/analyze'),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
      signal,
    },
    20000
  );
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
  },
  signal?: AbortSignal
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

  const res = await fetchWithTimeout(
    getApiUrl('/api/screen'),
    {
      method: 'POST',
      body: formData,
      signal,
    },
    120000
  );

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
export async function exportCsv(
  rankings: CandidateRanking[],
  jobTitle?: string,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetchWithTimeout(
    getApiUrl('/api/export'),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_title: jobTitle || 'Screening Results',
        rankings,
      }),
      signal,
    },
    30000
  );

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

/**
 * Validates a candidate resume and generates AI fit analysis & interview questions using Google Gemini.
 */
export async function validateResumeWithGemini(
  payload: ValidateResumeRequest,
  signal?: AbortSignal
): Promise<GeminiValidationResponse> {
  const res = await fetchWithTimeout(
    getApiUrl('/api/resumes/validate'),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
      signal,
    },
    45000
  );

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Failed to validate with Gemini' }));
    throw new Error(errorData.detail || `Server error ${res.status}`);
  }

  return res.json();
}
