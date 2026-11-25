import React, { useState, useEffect, useRef } from 'react';
import {
  Briefcase,
  FileText,
  UploadCloud,
  X,
  Clock,
  Sparkles,
  Loader2,
  FileUp,
  AlertCircle,
  AlertTriangle,
} from 'lucide-react';
import type { SampleJobItem, SampleResumeItem, JobAnalyzeResponse } from '../types/api.ts';
import { analyzeJob, fetchSampleResumeFile } from '../services/api.ts';
import { formatBytes, validateResumeFile, MAX_RESUMES } from '../utils/helpers.ts';

interface SetupSectionProps {
  jobText: string;
  onJobTextChange: (text: string) => void;
  sampleJobs: SampleJobItem[];
  sampleResumes: SampleResumeItem[];
  files: File[];
  onFilesChange: (files: File[]) => void;
  onToast: (msg: string, type?: 'info' | 'error' | 'success') => void;
}

export const SetupSection: React.FC<SetupSectionProps> = ({
  jobText,
  onJobTextChange,
  sampleJobs,
  sampleResumes,
  files,
  onFilesChange,
  onToast,
}) => {
  const [jobAnalysis, setJobAnalysis] = useState<JobAnalyzeResponse | null>(null);
  const [isAnalyzingJob, setIsAnalyzingJob] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoadingSamples, setIsLoadingSamples] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Debounced live preview call to /api/jobs/analyze (350ms) with cancellation
  useEffect(() => {
    if (!jobText.trim()) {
      setJobAnalysis(null);
      return;
    }

    const controller = new AbortController();
    setIsAnalyzingJob(true);
    const timer = setTimeout(async () => {
      try {
        const res = await analyzeJob(jobText, controller.signal);
        setJobAnalysis(res);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') {
          return;
        }
        // quiet error on preview debounce
      } finally {
        setIsAnalyzingJob(false);
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [jobText]);

  // Handle sample job selection
  const handleSelectSampleJob = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedId = e.target.value;
    if (!selectedId) return;
    const found = sampleJobs.find((j) => j.id === selectedId);
    if (found) {
      onJobTextChange(found.text);
      onToast(`Loaded sample: ${found.title}`, 'info');
    }
  };

  // Handle "Use sample resumes" button
  const handleUseSampleResumes = async () => {
    if (!sampleResumes || sampleResumes.length === 0) {
      onToast('No sample resumes available on backend.', 'error');
      return;
    }

    setIsLoadingSamples(true);
    try {
      const loadedFiles: File[] = [];
      for (const item of sampleResumes.slice(0, 10)) {
        const file = await fetchSampleResumeFile(item.filename);
        loadedFiles.push(file);
      }
      onFilesChange(loadedFiles);
      onToast(`Loaded ${loadedFiles.length} synthetic sample resumes.`, 'success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load sample resumes';
      onToast(msg, 'error');
    } finally {
      setIsLoadingSamples(false);
    }
  };

  // Handle file addition with client validation
  const handleAddFiles = (incomingFiles: FileList | File[]) => {
    const fileArray = Array.from(incomingFiles);
    const validToAdd: File[] = [];

    for (const file of fileArray) {
      // Check duplicate
      if (files.some((f) => f.name === file.name && f.size === file.size)) {
        continue;
      }

      const check = validateResumeFile(file);
      if (!check.valid) {
        onToast(check.error || 'Invalid file', 'error');
        continue;
      }

      validToAdd.push(file);
    }

    if (files.length + validToAdd.length > MAX_RESUMES) {
      onToast(`Maximum ${MAX_RESUMES} resumes allowed per batch. Excess files ignored.`, 'error');
      const allowed = validToAdd.slice(0, MAX_RESUMES - files.length);
      onFilesChange([...files, ...allowed]);
      return;
    }

    if (validToAdd.length > 0) {
      onFilesChange([...files, ...validToAdd]);
      onToast(`Added ${validToAdd.length} resume${validToAdd.length > 1 ? 's' : ''}.`, 'info');
    }
  };

  const handleRemoveFile = (index: number) => {
    const updated = files.filter((_, i) => i !== index);
    onFilesChange(updated);
  };

  // Drag-and-drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(e.dataTransfer.files);
    }
  };

  return (
    <section className="grid grid-cols-1 lg:grid-cols-2 gap-6" aria-label="Screening setup inputs">
      {/* ---------------------------------------------------- */}
      {/* CARD 1: Job Description */}
      {/* ---------------------------------------------------- */}
      <div className="bg-theme-surface border border-theme-border rounded-2xl p-5 shadow-card transition-colors flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-theme-border/80 mb-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-theme-tint/60 text-theme-primary flex items-center justify-center">
                <Briefcase className="w-4 h-4" />
              </div>
              <h2 className="text-sm font-semibold text-theme-ink uppercase tracking-wider">
                1. Target Job Description
              </h2>
            </div>

            {/* Sample Job Dropdown */}
            {sampleJobs.length > 0 && (
              <div className="flex items-center space-x-1.5">
                <label htmlFor="sample-job-select" className="text-xs text-theme-secondary-text sr-only">
                  Select sample job
                </label>
                <select
                  id="sample-job-select"
                  onChange={handleSelectSampleJob}
                  defaultValue=""
                  className="text-xs font-medium bg-theme-subtle text-theme-ink border border-theme-border rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-theme-primary cursor-pointer"
                  aria-label="Use sample job dropdown"
                >
                  <option value="" disabled>
                    Use sample job...
                  </option>
                  {sampleJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Textarea */}
          <div className="relative">
            <textarea
              id="job-description-textarea"
              value={jobText}
              onChange={(e) => onJobTextChange(e.target.value)}
              placeholder="Paste the target job description here (e.g. Job Title, Requirements, Experience, Preferred qualifications)..."
              rows={8}
              className="w-full text-sm font-mono bg-theme-canvas/50 border border-theme-border rounded-xl p-3.5 text-theme-ink placeholder:text-theme-secondary-text focus:outline-none focus:ring-2 focus:ring-theme-primary transition resize-y"
              aria-label="Job description text"
            />
          </div>
        </div>

        {/* Live Preview Section */}
        <div className="mt-4 pt-3.5 border-t border-theme-border/80">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-theme-secondary-text flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-theme-primary" />
              <span>Live Extracted Requirements</span>
            </span>
            {isAnalyzingJob && (
              <span className="text-xs text-theme-secondary-text flex items-center space-x-1">
                <Loader2 className="w-3 h-3 animate-spin text-theme-primary" />
                <span>Parsing...</span>
              </span>
            )}
          </div>

          {/* Multi-Job Detection Warning */}
          {jobAnalysis?.has_multiple_jobs && (
            <div className="mb-3 p-3 rounded-xl bg-theme-secondary/50 border border-theme-secondary/80 text-theme-hover text-xs flex items-start space-x-2.5">
              <AlertTriangle className="w-4 h-4 text-theme-hover shrink-0 mt-0.5" />
              <div>
                <span className="font-bold block">Multiple Job Postings Detected</span>
                <p className="mt-0.5 text-theme-hover">
                  {jobAnalysis.multiple_jobs_warning || 'This text appears to contain multiple job roles or postings. Requirements across sections were extracted, but for the most accurate screening results, evaluate one job at a time.'}
                </p>
              </div>
            </div>
          )}

          {jobAnalysis && (jobAnalysis.required_skills.length > 0 || jobAnalysis.preferred_skills.length > 0 || jobAnalysis.min_experience_years !== null) ? (
            <div className="space-y-2.5 text-xs">
              {/* Min Experience */}
              {jobAnalysis.min_experience_years !== null && jobAnalysis.min_experience_years !== undefined && (
                <div className="flex items-center space-x-1.5 text-theme-secondary-text">
                  <Clock className="w-3.5 h-3.5 text-theme-hover" />
                  <span className="font-semibold">Experience Gate:</span>
                  <span className="bg-theme-secondary/60 text-theme-hover px-2 py-0.5 rounded font-mono font-medium">
                    {jobAnalysis.min_experience_years}+ years minimum
                  </span>
                </div>
              )}

              {/* Required Skills Chips */}
              {jobAnalysis.required_skills.length > 0 && (
                <div>
                  <span className="text-theme-secondary-text block mb-1 font-medium">
                    Required Skills ({jobAnalysis.required_skills.length}):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {jobAnalysis.required_skills.map((s) => (
                      <span
                        key={s}
                        className="inline-flex items-center px-2 py-0.5 rounded-md border bg-theme-tint/60 text-theme-primary border-theme-secondary text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Preferred Skills Chips */}
              {jobAnalysis.preferred_skills.length > 0 && (
                <div>
                  <span className="text-theme-secondary-text block mb-1 font-medium">
                    Preferred Skills ({jobAnalysis.preferred_skills.length}):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {jobAnalysis.preferred_skills.map((s) => (
                      <span
                        key={s}
                        className="inline-flex items-center px-2 py-0.5 rounded-md border bg-theme-tint/60 text-theme-secondary-text border-theme-border text-xs font-medium"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-theme-secondary-text italic py-1">
              Type or select a job description above to preview extracted skill taxonomy and minimum experience gate.
            </div>
          )}
        </div>
      </div>

      {/* ---------------------------------------------------- */}
      {/* CARD 2: Candidate Resumes */}
      {/* ---------------------------------------------------- */}
      <div className="bg-theme-surface border border-theme-border rounded-2xl p-5 shadow-card transition-colors flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-3 border-b border-theme-border/80 mb-4">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-theme-tint/60 text-theme-ink flex items-center justify-center">
                <FileText className="w-4 h-4" />
              </div>
              <h2 className="text-sm font-semibold text-theme-ink uppercase tracking-wider">
                2. Candidate Resumes
              </h2>
            </div>

            {/* Use sample resumes button */}
            <button
              onClick={handleUseSampleResumes}
              disabled={isLoadingSamples}
              className="inline-flex items-center space-x-1.5 text-xs font-medium bg-theme-subtle text-theme-ink border border-theme-border rounded-lg px-2.5 py-1.5 hover:bg-theme-tint transition disabled:opacity-50"
              aria-label="Load synthetic test resumes"
            >
              {isLoadingSamples ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Loading...</span>
                </>
              ) : (
                <>
                  <FileUp className="w-3.5 h-3.5 text-theme-primary" />
                  <span>Use Sample Resumes</span>
                </>
              )}
            </button>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
              isDragging
                ? 'border-theme-primary bg-theme-tint/30'
                : 'border-theme-border hover:border-theme-hover bg-theme-canvas/30'
            }`}
            role="button"
            tabIndex={0}
            aria-label="Upload resume files drag and drop zone"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleAddFiles(e.target.files);
                  e.target.value = '';
                }
              }}
              className="hidden"
              aria-label="File upload input"
            />
            <div className="w-10 h-10 rounded-full bg-theme-subtle text-theme-secondary-text mx-auto flex items-center justify-center mb-2">
              <UploadCloud className="w-5 h-5 text-theme-primary" />
            </div>
            <p className="text-xs font-semibold text-theme-ink">
              Drag & drop resumes here, or <span className="text-theme-primary underline">browse</span>
            </p>
            <p className="text-[11px] text-theme-secondary-text mt-1">
              Supports PDF and DOCX files up to 5 MB (max {MAX_RESUMES} candidates per batch)
            </p>
          </div>
        </div>

        {/* Selected File Chips */}
        <div className="mt-4 pt-3.5 border-t border-theme-border/80">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-theme-secondary-text">
              Selected Resumes ({files.length} / {MAX_RESUMES})
            </span>
            {files.length > 0 && (
              <button
                onClick={() => onFilesChange([])}
                className="text-[11px] hover:text-theme-hover text-theme-hover font-medium transition"
              >
                Clear all
              </button>
            )}
          </div>

          {files.length > 0 ? (
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto pr-1">
              {files.map((file, idx) => (
                <div
                  key={`${file.name}-${idx}`}
                  className="inline-flex items-center space-x-2 bg-theme-subtle/80 text-theme-ink border border-theme-border px-2.5 py-1 rounded-lg text-xs"
                >
                  <FileText className="w-3.5 h-3.5 text-theme-primary flex-shrink-0" />
                  <span className="font-medium truncate max-w-[140px]" title={file.name}>
                    {file.name}
                  </span>
                  <span className="text-[10px] text-theme-secondary-text">({formatBytes(file.size)})</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveFile(idx);
                    }}
                    className="text-theme-secondary-text hover:text-theme-hover transition ml-1"
                    title={`Remove ${file.name}`}
                    aria-label={`Remove ${file.name}`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 text-xs text-theme-secondary-text italic py-2">
              <AlertCircle className="w-3.5 h-3.5 text-theme-secondary-text" />
              <span>No resumes selected. Upload files or click "Use Sample Resumes".</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
