import { Component, lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Activity, BarChart3, ChevronRight, CircleHelp, ClipboardList, FilePlus2, FileText, GitCompareArrows, LayoutDashboard, Menu, Moon, Plus, Settings, Sparkles, Star, Sun, Users, X } from 'lucide-react';
import Landing, { Brand } from './components/Landing';
import { ScreeningWorkspace, WeightControls } from './components/ScreeningWorkspace';
import type { Draft } from './components/ScreeningWorkspace';
import { CandidateDetail, Compare, EmptyResults, Insights, Leaderboard, Reports } from './components/CandidateWorkspace';
import { useTheme } from './context/ThemeContext';
import { readConfig, readModelInfo, screenResumes, serviceStatus } from './services/api';
import type { ModelInfo, ScreenResponse, ServiceConfig } from './types/api';
import { candidateId, DEFAULT_WEIGHTS, EMPTY_OVERRIDES } from './utils/workspace';
import './workspace.css';

const Distribution = lazy(() => import('./components/WorkspaceCharts').then(module => ({ default: module.Distribution })));
const navigation = [
  ['', 'Dashboard', LayoutDashboard], ['new', 'New screening', FilePlus2], ['candidates', 'Candidates', Users],
  ['compare', 'Comparison', GitCompareArrows], ['insights', 'AI insights', Sparkles], ['reports', 'Reports', ClipboardList],
  ['settings', 'Settings', Settings], ['status', 'System status', Activity],
] as const;
const URL = '/workspace';
const freshDraft = (): Draft => ({ text: '', overrides: { ...EMPTY_OVERRIDES }, files: [], samples: false });
const labels = {
  checking: 'Checking connection', ready: 'All systems operational', initializing: 'Models initializing',
  failed: 'Model initialization failed', unavailable: 'Backend unavailable', offline: 'Network disconnected',
  updateRequired: 'Backend update required',
};
type Status = keyof typeof labels;
type ActivityItem = { id: number; title: string; date: Date; total: number; shortlisted: number; average: number };

function useSystem() {
  const [status, setStatus] = useState<Status>('checking');
  const [config, setConfig] = useState<ServiceConfig>();
  const [model, setModel] = useState<ModelInfo>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (!navigator.onLine) setStatus('offline');
      else try {
        const state = await serviceStatus(controller.signal);
        if (!controller.signal.aborted) setStatus(state);
      } catch {
        if (!controller.signal.aborted) setStatus('unavailable');
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 25000);
    }
    void poll();
    readConfig(controller.signal).then(setConfig).catch(() => {});
    readModelInfo(controller.signal).then(setModel).catch(() => {});
    return () => { controller.abort(); clearTimeout(timer); };
  }, [attempt]);
  return { status, config, model, retry: () => setAttempt(value => value + 1) };
}

function Dashboard({ session, shortlisted, history, onNew }: { session?: ScreenResponse; shortlisted: Set<string>; history: ActivityItem[]; onNew: () => void }) {
  const total = history.reduce((sum, item) => sum + item.total, 0);
  const average = total ? history.reduce((sum, item) => sum + item.average * item.total, 0) / total : null;
  const activeShortlists = history.reduce((sum, item, i) => sum + (i === 0 ? shortlisted.size : item.shortlisted), 0);
  const metrics = [
    ['Resumes analyzed', total, FileText], ['Shortlisted candidates', activeShortlists, Star],
    ['Average match', average == null ? '—' : `${average.toFixed(1)}%`, BarChart3], ['Screening sessions', history.length, ClipboardList],
  ] as const;
  return <div className="stack">
    <div className="metrics">{metrics.map(([title, value, Icon]) => <article className="panel metric" key={title}><div className="feature-icon"><Icon size={18} /></div><strong>{value}</strong><span>{title}</span></article>)}</div>
    <div className="dashboard-grid">
      <section className="panel stack"><div className="panel-heading"><div><h2>Score distribution</h2><p>Match scores from your latest screening.</p></div><BarChart3 className="muted" size={20} /></div>
        {session ? <Suspense fallback={<p role="status">Loading chart…</p>}><Distribution rankings={session.rankings} /></Suspense> : <div className="chart-empty"><BarChart3 size={26} /><p>Screen a batch to see its match scores.</p></div>}</section>
      <section className="panel stack"><div className="panel-heading"><div><h2>Top candidates</h2><p>{session?.job.job_title || 'Latest screening'}</p></div>{session && <Link to={`${URL}/candidates`}>View all</Link>}</div>
        {session ? <div className="stack">{session.rankings.slice(0, 5).map(item => <Link className="profile-row" to={`${URL}/candidates/${encodeURIComponent(candidateId(item))}`} key={candidateId(item)}><span className="profile-avatar"><Users size={16} /></span><span>{item.candidate}</span><strong className="score-pill">{item.match_score.toFixed(1)}%</strong></Link>)}</div> : <div className="chart-empty"><Users size={26} /><p>Your ranked candidates will appear here.</p></div>}</section>
    </div>
    <section className="panel stack"><div className="panel-heading"><div><h2>Recent screenings</h2><p>Activity in this browser tab.</p></div><button className="button secondary" onClick={onNew}><Plus size={17} /> New session</button></div>
      {history.length ? history.map(item => <div className="activity-row" key={item.id}><div className="feature-icon"><ClipboardList size={18} /></div><div><strong>{item.title}</strong><p>{item.total} candidates · {item.date.toLocaleString()}</p></div><span className="score-pill">{item.average.toFixed(1)}% avg.</span></div>) : <p className="muted">No sessions recorded yet.</p>}</section>
  </div>;
}

function Workspace() {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const system = useSystem();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [draft, setDraft] = useState(freshDraft);
  const [weights, setWeights] = useState(DEFAULT_WEIGHTS);
  const [session, setSession] = useState<ScreenResponse>();
  const [history, setHistory] = useState<ActivityItem[]>([]);
  const [shortlisted, setShortlisted] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef<AbortController>();
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => { window.scrollTo(0, 0); }, [location.pathname]);
  useEffect(() => {
    if (!mobileOpen) return;
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [mobileOpen]);

  const section = location.pathname.split('/')[2] || '';
  const detail = location.pathname.split('/').length > 3 && section === 'candidates';
  const pageTitle = detail ? 'Candidate analysis' : navigation.find(([key]) => key === section)?.[1] || 'Dashboard';
  function newSession() { navigate(`${URL}/new`); }
  function updateSet(setter: typeof setShortlisted, id: string) {
    setter(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function run() {
    if (pending.current || system.status !== 'ready') return;
    const controller = new AbortController();
    pending.current = controller;
    setRunning(true); setError('');
    try {
      const result = await screenResumes(draft.text, draft.files, weights, { useSampleResumes: draft.samples, overrides: draft.overrides }, controller.signal);
      if (controller.signal.aborted) return;
      const now = new Date();
      const average = result.rankings.reduce((sum, item) => sum + item.match_score, 0) / result.total_candidates;
      setHistory(previous => [{ id: now.getTime(), title: result.job.job_title || 'Screening session', date: now, total: result.total_candidates, average, shortlisted: 0 }, ...previous.map((item, i) => i ? item : { ...item, shortlisted: shortlisted.size })]);
      setSession(result); setShortlisted(new Set()); setSelected(new Set()); setDraft(freshDraft());
      navigate(`${URL}/candidates`);
    } catch (cause) {
      if (!controller.signal.aborted) setError((cause as Error).message);
    } finally {
      pending.current = undefined;
      if (!controller.signal.aborted) setRunning(false);
    }
  }

  const unavailable = system.status !== 'ready' && system.status !== 'checking';
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to main content</a>
    <aside className={`sidebar ${mobileOpen ? 'is-open' : ''}`}>
      <div className="sidebar-top"><Brand /><button className="icon-button close-menu" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={21} /></button></div>
      <div className="side-label">WORKSPACE</div>
      <nav aria-label="Workspace">{navigation.map(([key, label, Icon]) => <NavLink key={key} end={!key} to={key ? `${URL}/${key}` : URL} onClick={() => setMobileOpen(false)}><Icon size={19} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-footer"><Link to="/#workflow"><CircleHelp size={17} /> How it works</Link><p>Human review required</p></div>
    </aside>
    {mobileOpen && <button className="mobile-scrim" aria-label="Dismiss navigation" onClick={() => setMobileOpen(false)} />}
    <div className="body-shell">
      <header className="app-header"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={() => setMobileOpen(!mobileOpen)}><Menu size={21} /></button><Link to={URL}>Workspace</Link><ChevronRight size={15} /><span>{pageTitle}</span></div><div className="action-row"><Link to={`${URL}/status`} className={`status-badge ${system.status}`}><i />{labels[system.status]}</Link><button className="icon-button" onClick={theme.toggleTheme} aria-label={`Switch to ${theme.theme === 'dark' ? 'light' : 'dark'} mode`}>{theme.theme === 'dark' ? <Sun size={19} /> : <Moon size={19} />}</button></div></header>
      <main id="main" className="app-main" tabIndex={-1}>
        <header className="page-heading"><div><h1>{pageTitle}</h1><p>{section === '' ? 'Review screening activity and candidate matches.' : section === 'new' ? 'Set the role requirements and upload candidate resumes.' : section === 'candidates' ? 'Review the evidence behind each match and build your shortlist.' : section === 'insights' ? 'Prepare job-specific questions with Gemini.' : ''}</p></div>{!section && <button className="button primary" onClick={newSession}><Plus size={19} /> New screening</button>}</header>
        {unavailable && section !== 'status' && <div className="notice" role="status"><Activity size={18} /><span>{labels[system.status]}. {system.status === 'unavailable' ? 'Render may be waking up.' : 'Check service status for details.'}</span><button className="button secondary" onClick={system.retry}>Check again</button></div>}
        {section === 'candidates' && !!session?.file_errors.length && <div className="notice" role="status"><ul>{session.file_errors.map((item, index) => <li key={index}>{item.filename} · {item.error}</li>)}</ul></div>}
        <Routes>
          <Route index element={<Dashboard session={session} shortlisted={shortlisted} history={history} onNew={newSession} />} />
          <Route path="new" element={<ScreeningWorkspace draft={draft} setDraft={setDraft} weights={weights} setWeights={setWeights} onRun={run} running={running} error={error} ready={system.status === 'ready'} config={system.config} />} />
          <Route path="candidates" element={session ? <Leaderboard key={history[0]?.id} session={session} shortlisted={shortlisted} selected={selected} toggleShortlist={id => updateSet(setShortlisted, id)} toggleSelection={id => updateSet(setSelected, id)} /> : <EmptyResults />} />
          <Route path="candidates/:id" element={session ? <DetailsRoute session={session} shortlisted={shortlisted} toggle={id => updateSet(setShortlisted, id)} /> : <EmptyResults />} />
          <Route path="compare" element={session ? <Compare session={session} selected={selected} /> : <EmptyResults />} />
          <Route path="insights" element={session ? <InsightsRoute session={session} /> : <EmptyResults />} />
          <Route path="reports" element={session ? <Reports session={session} shortlisted={shortlisted} /> : <EmptyResults />} />
          <Route path="settings" element={<div className="content-grid">
            <section className="panel stack"><h2>Appearance</h2><div className="action-row">{(['light', 'dark', 'studio'] as const).map(mode => <button className="button secondary" key={mode} aria-pressed={mode === 'dark' ? theme.theme === 'dark' : theme.theme === 'light' && (theme.preset === 'studio') === (mode === 'studio')} onClick={() => { theme.setPreset(mode === 'studio' ? 'studio' : 'dashboard'); theme.setTheme(mode === 'dark' ? 'dark' : 'light'); }}>{mode[0].toUpperCase() + mode.slice(1)}</button>)}</div><h2>Data handling</h2><p className="muted">Results live in this tab. Uploads are processed for the request. Gemini receives submitted excerpts only when you request insights.</p><Link to="/workspace/status">View model and API status</Link></section>
            <section className="panel stack"><h2>Scoring defaults</h2><WeightControls weights={weights} onChange={setWeights} /></section></div>} />
          <Route path="status" element={<section className="panel stack"><div className="panel-heading"><div><h2>{labels[system.status]}</h2><p>Readiness is checked every 25 seconds.</p></div><button className="button secondary" onClick={system.retry}>Check again</button></div>
            {system.status === 'unavailable' && <p>Check the network connection or allow Render time to wake up.</p>}
            {system.status === 'updateRequired' && <p>The service is running an earlier release. Screening resumes once the backend serves the current API.</p>}
            {system.status === 'failed' && <p>The backend is responding. The service owner can review model startup logs and restart the service.</p>}
            {system.status === 'initializing' && <p>The screening models are loading. Try again once the service is ready.</p>}
            <dl className="status-grid"><dt>Screening limits</dt><dd>{system.config ? `${system.config.max_resumes_per_batch} files · ${system.config.max_file_size_bytes / 1024 ** 2} MB each · ${system.config.max_batch_size_bytes / 1024 ** 2} MB per batch` : 'Unavailable'}</dd>
            <dt>Semantic model</dt><dd>{system.model?.embedding || 'Unavailable'}</dd><dt>Skill extraction</dt><dd>{system.model?.skills || 'Unavailable'}</dd><dt>Keyword relevance</dt><dd>{system.model?.keyword || 'Unavailable'}</dd><dt>Gemini</dt><dd>{!system.config ? 'Unknown' : system.config.gemini_available ? `${system.model?.gemini || 'Configured'} · credentials present` : 'Unconfigured'}</dd></dl></section>} />
          <Route path="*" element={<Navigate to={URL} replace />} />
        </Routes>
      </main>
    </div>
  </div>;
}

function DetailsRoute({ session, shortlisted, toggle }: { session: ScreenResponse; shortlisted: Set<string>; toggle: (id: string) => void }) {
  const { id } = useParams();
  const candidate = session.rankings.find(item => candidateId(item) === id);
  return candidate ? <CandidateDetail candidate={candidate} session={session} shortlisted={shortlisted.has(id!)} toggle={() => toggle(id!)} /> : <Navigate to={`${URL}/candidates`} replace />;
}

function InsightsRoute({ session }: { session: ScreenResponse }) {
  const [params, setParams] = useSearchParams();
  const candidate = session.rankings.find(item => candidateId(item) === params.get('candidate')) ?? session.rankings[0];
  return <Insights key={candidateId(candidate)} session={session} candidate={candidate} onSelect={id => setParams({ candidate: id })} />;
}

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <main className="landing-section"><h1>The workspace could not load</h1><p>Reload to start a fresh session.</p><button className="button primary" onClick={() => window.location.reload()}>Reload HireLens</button></main> : this.props.children;
  }
}

export function App() {
  return <ErrorBoundary><Routes><Route index element={<Landing />} /><Route path="/workspace/*" element={<Workspace />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes></ErrorBoundary>;
}
