import type {
  HealthResponse, HybridWeights, JobOverrides, InsightsResponse, ServiceConfig, ModelInfo, ComparisonResult,
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
  (import.meta.env.PROD ? 'https://ai-resume-screening-3-1r1d.onrender.com' : '')
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
  weights: ScoringWeights | HybridWeights,
  options?: {
    useSampleResumes?: boolean;
    sampleResumeIds?: string[];
    overrides?: JobOverrides;
  },
  signal?: AbortSignal
): Promise<ScreenResponse> {
  const formData = new FormData();
  formData.append('job_text', jobText);
  for (const [name, value] of Object.entries(weights)) formData.append(name, String(value));
  for (const [name, value] of Object.entries(options?.overrides ?? {})) {
    if (value.trim()) formData.append(name, value.trim());
  }


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
      if (typeof errJson.detail === "string") {
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


async function requestJson<T>(path: string, options: RequestInit = {}, timeout = 8000): Promise<T> {
  const response = await fetchWithTimeout(getApiUrl(path), options, timeout);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export async function serviceStatus(signal?: AbortSignal) {
  const response = await fetchWithTimeout(getApiUrl('/api/ready'), { signal }, 8000);
  if (response.status === 404) return 'updateRequired';
  if (response.status !== 200 && response.status !== 503) throw new Error('Backend unavailable');
  const data = await response.json() as { status: 'ready' | 'initializing' | 'failed' };
  return data.status;
}

export const readConfig = (signal?: AbortSignal) => requestJson<ServiceConfig>('/api/config', { signal });
export const readModelInfo = (signal?: AbortSignal) => requestJson<ModelInfo>('/api/model-info', { signal });

export function readJobDocument(file: File, signal?: AbortSignal) {
  const body = new FormData();
  body.append('file', file);
  return requestJson<{ text: string }>('/api/jobs/document', { method: 'POST', body, signal }, 25000);
}

export function getInsights(payload: ValidateResumeRequest, signal?: AbortSignal) {
  return requestJson<InsightsResponse>('/api/insights', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal,
  }, 27000);
}

export function compareCandidates(candidates: CandidateRanking[], signal?: AbortSignal) {
  return requestJson<ComparisonResult>('/api/compare', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidates: candidates.map(candidate => ({ ...candidate, resume_snippet: undefined, text_hash: undefined })) }),
    signal,
  });
}
