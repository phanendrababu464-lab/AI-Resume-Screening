import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { FileText, Play, UploadCloud, X } from 'lucide-react';
import { analyzeJob, fetchSamples, readJobDocument } from '../services/api';
import { DEFAULT_WEIGHTS, EMPTY_OVERRIDES, WEIGHTS } from '../utils/workspace';
import type { HybridWeights, JobAnalyzeResponse, JobOverrides, SamplesResponse, ServiceConfig } from '../types/api';

export function WeightControls({ weights, onChange }: { weights: HybridWeights; onChange: (value: HybridWeights) => void }) {
  const sum = WEIGHTS.reduce((total, [key]) => total + Math.round(weights[key] * 100), 0);
  return <>
    <div className="field-grid">{WEIGHTS.map(([key, label]) => <label key={key}>{label} (%)
      <input type="number" min="0" max="100" step="1" value={Math.round(weights[key] * 100)}
        onChange={event => onChange({ ...weights, [key]: Math.min(100, Math.max(0, +event.target.value)) / 100 })} />
    </label>)}</div>
    <div className="controls-footer"><span className={sum === 100 ? 'muted' : 'error-text'}>Total {sum}%{sum !== 100 && ' · must equal 100%'}</span><button className="button secondary" type="button" onClick={() => onChange(DEFAULT_WEIGHTS)}>Reset defaults</button></div>
    <label className="checkbox"><input type="checkbox" checked={weights.anonymize} onChange={event => onChange({ ...weights, anonymize: event.target.checked })} /> Hide candidate filenames and excerpts in results</label>
  </>;
}

export interface Draft {
  text: string;
  overrides: JobOverrides;
  files: File[];
  samples: boolean;
}

export function ScreeningWorkspace({ draft, setDraft, weights, setWeights, onRun, running, error, config }: {
  draft: Draft;
  setDraft: (value: Draft) => void;
  weights: HybridWeights;
  setWeights: (value: HybridWeights) => void;
  onRun: () => void;
  running: boolean;
  error: string;
  config?: ServiceConfig;
}) {
  const [samples, setSamples] = useState<SamplesResponse>();
  const [loadingSample, setLoadingSample] = useState(false);
  const [localError, setLocalError] = useState('');
  const [draftAnalysis, setDraftAnalysis] = useState<JobAnalyzeResponse>();
  const [dragging, setDragging] = useState(false);
  const [importing, setImporting] = useState(false);
  const action = useRef<AbortController>();
  const input = useRef<HTMLInputElement>(null);
  const limit = config?.max_resumes_per_batch ?? 25;
  const fileLimit = config?.max_file_size_bytes ?? 5 * 1024 ** 2;
  const batchLimit = config?.max_batch_size_bytes ?? 25 * 1024 ** 2;
  const validWeights = WEIGHTS.reduce((sum, [key]) => sum + Math.round(weights[key] * 100), 0) === 100;

  useEffect(() => {
    if (!draft.text.trim()) return;
    const controller = new AbortController();
    const id = setTimeout(() => {
      analyzeJob(draft.text, controller.signal).then(value => { if (!controller.signal.aborted) setDraftAnalysis(value); }).catch(() => {});
    }, 550);
    return () => { clearTimeout(id); controller.abort(); };
  }, [draft.text]);

  useEffect(() => () => action.current?.abort(), []);

  async function loadSample() {
    const controller = new AbortController();
    action.current = controller;
    setLoadingSample(true);
    setLocalError('');
    try {
      const data = samples ?? await fetchSamples(controller.signal);
      if (!data.jobs.length || !data.resumes.length) throw new Error('Sample files are unavailable.');
      if (!controller.signal.aborted) {
        setSamples(data);
        setDraft({ text: data.jobs[0].text, overrides: { ...EMPTY_OVERRIDES, job_title: data.jobs[0].title }, files: [], samples: true });
      }
    } catch (cause) {
      if (!controller.signal.aborted) setLocalError((cause as Error).message);
    } finally {
      if (!controller.signal.aborted) setLoadingSample(false);
    }
  }

  async function importDocument(file?: File) {
    if (!file) return;
    const controller = new AbortController();
    action.current = controller;
    setImporting(true);
    setLocalError('');
    try {
      const response = await readJobDocument(file, controller.signal);
      if (!controller.signal.aborted) setDraft({ ...draft, text: response.text });
    } catch (cause) {
      if (!controller.signal.aborted) setLocalError((cause as Error).message);
    } finally {
      if (!controller.signal.aborted) setImporting(false);
    }
  }

  function addFiles(list: FileList) {
    const files = [...draft.files];
    let total = files.reduce((size, file) => size + file.size, 0);
    const rejected: string[] = [];
    for (const file of Array.from(list)) {
      if (files.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) continue;
      if (!/\.(pdf|docx)$/i.test(file.name) || !file.size || file.size > fileLimit) {
        rejected.push(`${file.name} must be a readable PDF or DOCX under ${fileLimit / 1024 ** 2} MB.`);
      } else if (files.length >= limit || total + file.size > batchLimit) {
        rejected.push('The batch exceeds the upload limits.');
        break;
      } else {
        total += file.size;
        files.push(file);
      }
    }
    setLocalError(rejected.join(' '));
    if (files.length > draft.files.length) setDraft({ ...draft, files, samples: false });
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.text.trim() && (draft.files.length || draft.samples) && validWeights) onRun();
  }

  const busy = running || importing || loadingSample;
  const detected = draft.text.trim() ? draftAnalysis : undefined;
  const fields = [
    ['job_title', 'Job title', detected?.job_title, 120],
    ['required_skills', 'Required skills', detected?.required_skills.join(', ') || 'Python, FastAPI', 1200],
    ['preferred_skills', 'Preferred skills', detected?.preferred_skills.join(', ') || 'Docker, AWS', 1200],
  ] as const;
  return <form className="stack" onSubmit={submit}>
    <fieldset className="screening-grid" disabled={busy}>
      <section className="panel stack">
        <div className="panel-heading"><div><h2>Job description</h2><p>Paste the role or import a PDF or DOCX.</p></div><label className="button secondary file-button">{importing ? 'Importing…' : 'Import document'}<input aria-label="Import job description document" type="file" accept=".pdf,.docx" onChange={event => { void importDocument(event.target.files?.[0]); event.target.value = ''; }} /></label></div>
        <label>Job description<textarea aria-label="Job description" required maxLength={24000} rows={9} placeholder="Describe the role and qualifications…" value={draft.text} onChange={event => { setDraftAnalysis(undefined); setDraft({ ...draft, text: event.target.value }); }} /></label>
        <div className="field-grid">{fields.map(([key, label, placeholder, max]) => <label key={key}>{label}<input maxLength={max} value={draft.overrides[key]} placeholder={placeholder || ''} onChange={event => setDraft({ ...draft, overrides: { ...draft.overrides, [key]: event.target.value } })} /></label>)}
        <label>Minimum experience (years)<input type="number" min="0" max="60" step="0.5" placeholder={String(detected?.min_experience_years ?? '')} value={draft.overrides.min_experience_years} onChange={event => setDraft({ ...draft, overrides: { ...draft.overrides, min_experience_years: event.target.value } })} /></label></div>
        <p className="muted">Leave criteria blank to use the qualifications detected in the description. Separate skills with commas.</p>
      </section>
      <section className="panel stack">
        <div className="panel-heading"><div><h2>Candidate resumes</h2><p>Up to {limit} files per batch.</p></div><button type="button" className="button secondary" onClick={loadSample}>{loadingSample ? 'Loading…' : 'Use sample batch'}</button></div>
        <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={event => { event.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) addFiles(event.dataTransfer.files); }}>
          <div className="feature-icon"><UploadCloud size={24} /></div><strong>Drag and drop resumes</strong><span>PDF or DOCX · up to {fileLimit / 1024 ** 2} MB each</span>
          <button type="button" className="button secondary" onClick={() => input.current?.click()}>Browse files</button>
          <input ref={input} className="sr-only" tabIndex={-1} aria-label="Upload resumes" type="file" accept=".pdf,.docx" multiple onChange={event => { if (event.target.files) addFiles(event.target.files); event.target.value = ''; }} />
        </div>
        {draft.samples && <div className="file-row"><FileText size={18} /><span>Synthetic resume batch</span><button type="button" className="icon-button" aria-label="Remove sample resumes" onClick={() => setDraft({ ...draft, samples: false })}><X size={17} /></button></div>}
        {draft.files.map((file, index) => <div className="file-row" key={`${file.name}-${index}`}><FileText size={18} /><span>{file.name}</span><button type="button" className="icon-button" aria-label={`Remove ${file.name}`} onClick={() => setDraft({ ...draft, files: draft.files.filter((_, i) => i !== index) })}><X size={17} /></button></div>)}
        {!draft.files.length && !draft.samples && <p className="muted">Your selected files will appear here.</p>}
      </section>
      <section className="panel weights-panel stack"><h2>Scoring weights</h2><WeightControls weights={weights} onChange={setWeights} /></section>
    </fieldset>
    {(localError || error) && <p className="notice danger" role="alert">{localError || error}</p>}
    <div className="controls-footer"><p className="muted">Review evidence before making a hiring decision.</p><button className="button primary" disabled={busy || !draft.text.trim() || (!draft.files.length && !draft.samples) || !validWeights}><Play size={17} />{running ? 'Screening resumes…' : error ? 'Retry screening' : 'Screen and rank'}</button></div>
    {running && <div className="panel loading" role="status">Reading resumes and calculating match scores…<div /><div /><div /></div>}
  </form>;
}
