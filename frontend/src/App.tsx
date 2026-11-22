import React, { useState, useEffect } from 'react';
import {
  TopBar,
} from './components/TopBar.tsx';
import {
  SetupSection,
} from './components/SetupSection.tsx';
import {
  ScoringSettings,
} from './components/ScoringSettings.tsx';
import {
  HowItWorksModal,
} from './components/HowItWorksModal.tsx';
import {
  SkeletonLoader,
} from './components/SkeletonLoader.tsx';
import {
  BestMatchHero,
} from './components/Results/BestMatchHero.tsx';
import {
  Leaderboard,
} from './components/Results/Leaderboard.tsx';
import {
  SkillMatchMatrix,
} from './components/Results/SkillMatchMatrix.tsx';
import {
  CandidateDetailDrawer,
} from './components/Results/CandidateDetailDrawer.tsx';
import {
  ExportButton,
} from './components/Results/ExportButton.tsx';
import {
  KpiTiles,
} from './components/Results/KpiTiles.tsx';

import type {
  SampleJobItem,
  SampleResumeItem,
  ScreenResponse,
  ScoringWeights,
} from './types/api.ts';
import { fetchSamples, screenResumes } from './services/api.ts';
import { useTheme } from './context/ThemeContext.tsx';
import {
  AlertCircle,
  CheckCircle2,
  Info,
  X,
  FileText,
  Sliders,
  TrendingUp,
  Award,
  Trophy,
  Layers,
  Target,
} from 'lucide-react';

const ScoreComposition = React.lazy(async () => {
  const { ScoreComposition } = await import('./components/Results/ScoreComposition.tsx');
  return { default: ScoreComposition };
});

interface ToastMessage {
  id: string;
  text: string;
  type: 'info' | 'error' | 'success';
}

const DEFAULT_WEIGHTS: ScoringWeights = {
  required_skill_weight: 0.50,
  preferred_skill_weight: 0.20,
  semantic_weight: 0.20,
  experience_weight: 0.10,
  experience_penalty: 0.60,
  anonymize: false,
};

export const App: React.FC = () => {
  const { preset } = useTheme();

  // Setup inputs
  const [jobText, setJobText] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [sampleJobs, setSampleJobs] = useState<SampleJobItem[]>([]);
  const [sampleResumes, setSampleResumes] = useState<SampleResumeItem[]>([]);

  // Scoring Weights
  const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);

  // Screening Execution & Results State
  const [isScreening, setIsScreening] = useState(false);
  const [results, setResults] = useState<ScreenResponse | null>(null);
  const [selectedCandidateName, setSelectedCandidateName] = useState<string | null>(null);

  // Modals & Toasts
  const [isExplainerOpen, setIsExplainerOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Toast dispatch
  const showToast = (text: string, type: 'info' | 'error' | 'success' = 'info') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Initial fetch of sample data with graceful retry if backend is waking up
  useEffect(() => {
    const controller = new AbortController();
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    const loadSamples = async (attemptsLeft = 2) => {
      try {
        const data = await fetchSamples(controller.signal);
        if (!controller.signal.aborted) {
          setSampleJobs(data.jobs || []);
          setSampleResumes(data.resumes || []);
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        if (attemptsLeft > 0) {
          retryTimer = setTimeout(() => {
            if (!controller.signal.aborted) loadSamples(attemptsLeft - 1);
          }, 6000);
        } else {
          console.warn('Could not load samples:', err);
        }
      }
    };

    loadSamples();
    return () => {
      controller.abort();
      clearTimeout(retryTimer);
    };
  }, []);

  // Validation logic for Run button
  const weightsSum = Math.round(
    (weights.required_skill_weight +
      weights.preferred_skill_weight +
      weights.semantic_weight +
      weights.experience_weight) *
      100
  ) / 100;
  const isWeightsValid = Math.abs(weightsSum - 1.0) <= 0.005;

  let disabledReason: string | null = null;
  if (!jobText.trim()) {
    disabledReason = 'Provide a target job description to begin screening.';
  } else if (files.length === 0) {
    disabledReason = 'Upload or select candidate resumes to screen.';
  } else if (!isWeightsValid) {
    disabledReason = `Scoring weights must sum to exactly 100% (currently ${Math.round(weightsSum * 100)}%).`;
  }

  const isValidToRun = disabledReason === null;

  // Execute Screening Action
  const handleRunScreening = async () => {
    if (!isValidToRun) return;

    setIsScreening(true);
    setResults(null);
    try {
      const response = await screenResumes(jobText, files, weights);
      setResults(response);
      showToast(`Successfully screened and ranked ${response.total_candidates} candidates!`, 'success');

      // Surface per-file errors if any occurred
      if (response.file_errors && response.file_errors.length > 0) {
        for (const fe of response.file_errors) {
          showToast(`Warning for ${fe.filename}: ${fe.error}`, 'error');
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Screening execution failed';
      showToast(msg, 'error');
    } finally {
      setIsScreening(false);
    }
  };

  // Selected candidate object for drawer
  const selectedCandidate = results?.rankings.find((r) => r.candidate === selectedCandidateName) || null;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      {/* 1. Top Bar with Preset Switcher and Theme Toggle */}
      <TopBar onOpenExplainer={() => setIsExplainerOpen(true)} />

      <div className="flex-1 flex relative">
        {/* Dashboard Preset: Slim Left Navigation Sidebar */}
        {preset === 'dashboard' && (
          <aside
            className="hidden lg:flex flex-col w-14 shrink-0 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 items-center py-5 space-y-4 sticky top-16 h-[calc(100vh-4rem)] z-30 transition-colors"
            aria-label="Dashboard navigation sidebar"
          >
            <button
              onClick={() => document.getElementById('setup-section')?.scrollIntoView({ behavior: 'smooth' })}
              className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
              title="Setup & Resumes"
              aria-label="Scroll to setup section"
            >
              <FileText className="w-5 h-5" />
            </button>
            <button
              onClick={() => document.getElementById('scoring-settings')?.scrollIntoView({ behavior: 'smooth' })}
              className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
              title="Scoring Weights"
              aria-label="Scroll to scoring settings"
            >
              <Sliders className="w-5 h-5" />
            </button>

            {results && (
              <>
                <div className="w-6 border-b border-slate-200 dark:border-slate-800 my-1" />
                <button
                  onClick={() => document.getElementById('results-kpi')?.scrollIntoView({ behavior: 'smooth' })}
                  className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="KPI Summary"
                  aria-label="Scroll to KPI summary"
                >
                  <TrendingUp className="w-5 h-5" />
                </button>
                <button
                  onClick={() => document.getElementById('results-hero')?.scrollIntoView({ behavior: 'smooth' })}
                  className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="Best Match"
                  aria-label="Scroll to best match hero"
                >
                  <Award className="w-5 h-5" />
                </button>
                <button
                  onClick={() => document.getElementById('results-leaderboard')?.scrollIntoView({ behavior: 'smooth' })}
                  className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="Leaderboard"
                  aria-label="Scroll to candidate leaderboard"
                >
                  <Trophy className="w-5 h-5" />
                </button>
                <button
                  onClick={() => document.getElementById('results-composition')?.scrollIntoView({ behavior: 'smooth' })}
                  className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="Score Composition"
                  aria-label="Scroll to score composition"
                >
                  <Layers className="w-5 h-5" />
                </button>
                <button
                  onClick={() => document.getElementById('results-matrix')?.scrollIntoView({ behavior: 'smooth' })}
                  className="p-2 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 dark:hover:text-sky-400 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                  title="Skill Matrix"
                  aria-label="Scroll to skill match matrix"
                >
                  <Target className="w-5 h-5" />
                </button>
              </>
            )}
          </aside>
        )}

        {/* Main Content Container */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
          {/* 2. Setup Section: 2 Cards Side by Side */}
          <div id="setup-section">
            <SetupSection
              jobText={jobText}
              onJobTextChange={setJobText}
              sampleJobs={sampleJobs}
              sampleResumes={sampleResumes}
              files={files}
              onFilesChange={setFiles}
              onToast={showToast}
            />
          </div>

          {/* 3. Scoring Settings Collapsible Panel */}
          <div id="scoring-settings">
            <ScoringSettings
              weights={weights}
              onWeightsChange={setWeights}
              isValidToRun={isValidToRun}
              disabledReason={disabledReason}
              isRunning={isScreening}
              onRun={handleRunScreening}
            />
          </div>

          {/* 4. Loading State Skeleton Placeholders */}
          {isScreening && <SkeletonLoader />}

          {/* 5. Results Section */}
          {results && !isScreening && (
            <div className="space-y-8 animate-fade-in" aria-label="Screening results section">
              {/* Header with Export Action */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
                <div>
                  <h2 className="text-xl font-extrabold text-slate-900 dark:text-slate-50 tracking-tight">
                    Evaluation & Candidate Ranking Results
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Screened {results.total_candidates} candidates against job taxonomy
                  </p>
                </div>

                {/* 5.f Export CSV Button */}
                <ExportButton
                  rankings={results.rankings}
                  jobTitle={results.job.job_title || 'Resume Screening'}
                  onToast={showToast}
                />
              </div>

              {/* Weight Redistribution Informational Note */}
              {results.weight_redistribution_note && (
                <div className="p-3 rounded-xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/80 text-blue-900 dark:text-blue-200 text-xs flex items-center space-x-2.5">
                  <Info className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0" />
                  <span>
                    <strong>Weight Redistribution:</strong> {results.weight_redistribution_note}
                  </span>
                </div>
              )}

              {/* Dashboard Preset: Top KPI Summary Tiles */}
              {preset === 'dashboard' && <KpiTiles results={results} />}

              {/* 5.a Best Match Hero Card */}
              <div id="results-hero">
                <BestMatchHero
                  recommendation={results.recommendation}
                  topCandidate={results.rankings[0]}
                  totalCandidates={results.total_candidates}
                  onOpenDetail={(name) => setSelectedCandidateName(name)}
                />
              </div>

              {/* 5.b Leaderboard (Horizontal Bars, sorted best first) */}
              <div id="results-leaderboard">
                <Leaderboard
                  rankings={results.rankings}
                  onSelectCandidate={(name) => setSelectedCandidateName(name)}
                  selectedCandidate={selectedCandidateName}
                />
              </div>

              {/* 5.c Score Composition (Stacked Horizontal Bars) */}
              <React.Suspense fallback={<p role="status">Loading score breakdown…</p>}>
                <ScoreComposition
                  compositionData={results.charts.composition}
                  rankings={results.rankings}
                  nonApplicableComponents={results.non_applicable_components || []}
                />
              </React.Suspense>

              {/* 5.d Skill Match Matrix (Grouped Columns, Symbols, Fixed Sizes) */}
              <div id="results-matrix">
                <SkillMatchMatrix
                  matrixData={results.charts.matrix}
                  rankings={results.rankings}
                  job={results.job}
                  onSelectCandidate={(name) => setSelectedCandidateName(name)}
                />
              </div>
            </div>
          )}

          {/* 5.e Candidate Detail Drawer */}
          <CandidateDetailDrawer
            candidate={selectedCandidate}
            jobText={results?.job.raw_text || ''}
            onClose={() => setSelectedCandidateName(null)}
          />
        </main>
      </div>

      {/* 6. Explainer Modal */}
      <HowItWorksModal
        isOpen={isExplainerOpen}
        onClose={() => setIsExplainerOpen(false)}
        weights={weights}
      />

      {/* Toast Notification Container */}
      <div className="fixed bottom-5 right-5 z-50 space-y-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start space-x-2.5 p-3.5 rounded-xl shadow-xl border text-xs transition-all transform translate-y-0 ${
              toast.type === 'error'
                ? 'bg-rose-50 text-rose-900 border-rose-200 dark:bg-rose-950 dark:text-rose-200 dark:border-rose-800'
                : toast.type === 'success'
                ? 'bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800'
                : 'bg-slate-900 text-white border-slate-700 dark:bg-slate-100 dark:text-slate-900'
            }`}
            role="alert"
          >
            {toast.type === 'error' ? (
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
            ) : toast.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" />
            ) : (
              <Info className="w-4 h-4 text-accent-400 flex-shrink-0 mt-0.5" />
            )}
            <span className="flex-1 font-medium leading-relaxed">{toast.text}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
              aria-label="Dismiss toast"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
