import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Download, GitCompareArrows, Search, Sparkles, Star } from 'lucide-react';
import { Link } from 'react-router-dom';
import { candidateId } from '../utils/workspace';
import { compareCandidates, exportCsv, getInsights } from '../services/api';
import type { CandidateRanking, ComparisonResult, InsightsResponse, ScreenResponse } from '../types/api';

const ComparisonChart = lazy(() => import('./WorkspaceCharts').then(module => ({ default: module.ComparisonChart })));
const PAGE_SIZE = 15;
const metric = (score?: number | null) => score == null ? '—' : `${Math.round(score * 100)}%`;
const overall = (score: number) => `${score.toFixed(1)}%`;


const columns = [
  ['rank', 'Rank', (c: CandidateRanking) => c.rank],
  ['candidate', 'Candidate', (c: CandidateRanking) => c.candidate],
  ['match', 'Overall', (c: CandidateRanking) => c.match_score],
  ['semantic', 'Semantic', (c: CandidateRanking) => c.component_scores.semantic_score],
  ['keyword', 'Keyword', (c: CandidateRanking) => c.component_scores.tfidf_baseline_score ?? -1],
  ['skill', 'Skills', (c: CandidateRanking) => c.component_scores.skill_score ?? -1],
  ['experience', 'Experience', (c: CandidateRanking) => c.component_scores.experience_score ?? -1],
] as const;

export function EmptyResults() {
  return <section className="panel empty"><div className="feature-icon"><Search size={24} /></div><h2>No screening results yet</h2><p>Screen a batch to see candidates and reports here.</p><Link className="button primary" to="/workspace/new">New screening</Link></section>;
}

export function Leaderboard({ session, shortlisted, selected, toggleShortlist, toggleSelection }: {
  session: ScreenResponse;
  shortlisted: Set<string>;
  selected: Set<string>;
  toggleShortlist: (id: string) => void;
  toggleSelection: (id: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState<{ key: (typeof columns)[number][0]; ascending: boolean }>({ key: 'rank', ascending: true });
  const [page, setPage] = useState(0);
  const accessor = columns.find(([key]) => key === sort.key)![2];
  const query = search.trim().toLowerCase();
  const rows = session.rankings.filter(candidate => {
    const isShortlisted = shortlisted.has(candidateId(candidate));
    return (filter === 'all' || (filter === 'shortlisted' ? isShortlisted : !isShortlisted))
      && [candidate.candidate, candidate.candidate_name ?? "", ...(candidate.detected_skills ?? candidate.matched_skills)].some(text => text.toLowerCase().includes(query));
  }).sort((a, b) => {
    const left = accessor(a);
    const right = accessor(b);
    const result = typeof left === 'string' ? left.localeCompare(String(right)) : left - Number(right);
    return sort.ascending ? result : -result;
  });
  const lastPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
  const activePage = Math.min(page, lastPage);
  return <section className="panel stack">
    <div className="panel-heading"><div><h2>{session.job.job_title || 'Screening results'}</h2><p>{session.total_candidates} screened · {shortlisted.size} shortlisted</p></div><div className="action-row"><Link className="button secondary" to="/workspace/reports"><Download size={16} /> Export</Link><Link className="button secondary" to="/workspace/compare"><GitCompareArrows size={16} /> Compare ({selected.size})</Link></div></div>
    <div className="filters"><label>Search candidates<input type="search" value={search} placeholder="Candidate or skill" onChange={event => { setSearch(event.target.value); setPage(0); }} /></label><label>Screening status<select value={filter} onChange={event => { setFilter(event.target.value); setPage(0); }}><option value="all">All candidates</option><option value="shortlisted">Shortlisted</option><option value="screened">Screened only</option></select></label></div>
    <div className="table-scroll"><table><thead><tr><th scope="col">Compare</th>{columns.map(([key, title]) => <th scope="col" key={key} aria-sort={key === sort.key ? (sort.ascending ? 'ascending' : 'descending') : 'none'}><button onClick={() => { setSort({ key, ascending: key === sort.key ? !sort.ascending : key === 'rank' || key === 'candidate' }); setPage(0); }}>{title}{key === sort.key && (sort.ascending ? ' ↑' : ' ↓')}</button></th>)}<th scope="col">Status</th><th scope="col">Details</th></tr></thead>
    <tbody>{rows.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE).map(candidate => {
      const id = candidateId(candidate);
      const scores = candidate.component_scores;
      return <tr key={id}><td><input type="checkbox" aria-label={`Compare ${candidate.candidate}`} checked={selected.has(id)} disabled={selected.size >= 6 && !selected.has(id)} onChange={() => toggleSelection(id)} /></td>
        <td>{candidate.rank_display || candidate.rank}</td><td className="candidate-name">{candidate.candidate_name || candidate.candidate}</td><td><span className="score-pill">{overall(candidate.match_score)}</span></td><td>{metric(scores.semantic_score)}</td><td>{metric(scores.tfidf_baseline_score)}</td><td>{metric(scores.skill_score)}</td><td>{metric(scores.experience_score)}</td>
        <td><button className="shortlist" aria-pressed={shortlisted.has(id)} onClick={() => toggleShortlist(id)} aria-label={`Shortlist ${candidate.candidate}`}><Star size={15} />{shortlisted.has(id) ? 'Shortlisted' : 'Screened'}</button></td>
        <td><Link to={`/workspace/candidates/${encodeURIComponent(id)}`}>View<span className="sr-only"> {candidate.candidate}</span></Link></td></tr>;
    })}</tbody></table></div>
    {!rows.length && <p className="muted">No candidates match your search and filters.</p>}
    {lastPage > 0 && <div className="controls-footer"><span>Page {activePage + 1} of {lastPage + 1}</span><div className="action-row"><button className="button secondary" disabled={!activePage} onClick={() => setPage(activePage - 1)}>Previous</button><button className="button secondary" disabled={activePage === lastPage} onClick={() => setPage(activePage + 1)}>Next</button></div></div>}
  </section>;
}

function List({ items }: { items: string[] }) {
  return items.length ? <ul className="simple-list">{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="muted">No evidence recorded.</p>;
}

export function CandidateDetail({ candidate, session, shortlisted, toggle }: { candidate: CandidateRanking; session: ScreenResponse; shortlisted: boolean; toggle: () => void }) {
  const scores = candidate.component_scores;
  const id = candidateId(candidate);
  const points = session.charts.composition.filter(item => item.candidate === candidate.candidate);
  const resume = candidate.resume_snippet;
  return <div className="stack">
    <div className="controls-footer"><Link to="/workspace/candidates">Back to candidates</Link><div className="action-row"><button className="button secondary" onClick={toggle} aria-pressed={shortlisted}><Star size={17} />{shortlisted ? 'Shortlisted' : 'Shortlist candidate'}</button><Link className="button primary" to={`/workspace/insights?candidate=${encodeURIComponent(id)}`}><Sparkles size={17} /> AI insights</Link></div></div>
    <section className="panel"><h2>{candidate.candidate_name || candidate.candidate}</h2>{candidate.resume_filename && <p className="muted">{candidate.resume_filename}</p>}</section>
    <div className="content-grid"><section className="panel stack"><p className="eyebrow">MATCH SCORE</p><h2 className="big-score">{overall(candidate.match_score)}</h2><p className="muted">Rank {candidate.rank_display || candidate.rank} · {session.job.job_title || 'Screening session'}</p><div className="metric-list">{[['Semantic similarity', scores.semantic_score], ['Keyword relevance', scores.tfidf_baseline_score], ['Skill match', scores.skill_score], ['Experience relevance', scores.experience_score]].map(([label, score], index) => <div key={String(label)}><span>{label}</span><meter min={0} max={1} value={Number(score ?? 0)} aria-label={String(label)} /><strong>{metric(score as number | null)}</strong><small>{points[index] ? `+${points[index].contribution.toFixed(2)} pts` : ''}</small></div>)}</div></section>
    <section className="panel stack"><h2>Evidence and qualifications</h2><div><h3>Detected technical skills</h3><List items={candidate.detected_skills ?? candidate.matched_skills} /></div><div><h3>Required skills without evidence</h3><List items={candidate.missing_required_skills} /></div><div><h3>Experience to verify</h3><p>{candidate.experience_years == null ? 'Years of relevant experience are unknown.' : `The resume states ${candidate.experience_years} years of experience. Confirm its relevance in an interview.`}</p>{session.job.min_experience_years != null && <p className="muted">Role minimum: {session.job.min_experience_years} years.</p>}</div></section></div>
    <section className="panel stack"><h2>Resume excerpt</h2>{resume ? <pre className="excerpt">{resume}</pre> : <p className="muted">This session hides candidate excerpts.</p>}</section>
  </div>;
}

export function Compare({ session, selected }: { session: ScreenResponse; selected: Set<string> }) {
  const [data, setData] = useState<ComparisonResult>();
  const [error, setError] = useState('');
  const [attempt, retry] = useState(0);
  useEffect(() => {
    setData(undefined); setError('');
    if (selected.size < 2) return;
    const controller = new AbortController();
    compareCandidates(session.rankings.filter(candidate => selected.has(candidateId(candidate))), controller.signal)
      .then(setData).catch(cause => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [session, selected, attempt]);
  return <section className="panel stack"><div className="panel-heading"><div><h2>Compare selected candidates</h2><p>Select two to six candidates in the leaderboard.</p></div><Link className="button secondary" to="/workspace/candidates">Candidate leaderboard</Link></div>
    {selected.size < 2 ? <p className="muted">{selected.size} selected. Choose at least two candidates.</p> : error ? <><p className="notice danger" role="alert">{error}</p><button className="button secondary" onClick={() => retry(attempt + 1)}>Retry comparison</button></> : !data ? <p role="status">Loading comparison…</p> : <>
      <Suspense fallback={<p role="status">Loading chart…</p>}><ComparisonChart {...data} /></Suspense>
      <div className="table-scroll"><table><thead><tr><th>Measure</th>{data.candidates.map(candidate => <th key={candidate.id}>{candidate.label}</th>)}</tr></thead><tbody>
        {([
          ['Overall match', (c: ComparisonResult['candidates'][number]) => overall(c.overall)],
          ['Semantic similarity', c => metric(c.scores.semantic_score)],
          ['Required skills coverage', c => metric(c.scores.required_skill_score)],
          ['Preferred skills coverage', c => metric(c.scores.preferred_skill_score)],
          ['Experience relevance', c => metric(c.scores.experience_score)],
          ['Detected matches', c => c.matched.join(', ') || '—'],
          ['Required skills to verify', c => c.missing.join(', ') || '—'],
        ] as Array<[string, (c: ComparisonResult["candidates"][number]) => string]> ).map(([label, read]) => <tr key={String(label)}><th scope="row">{String(label)}</th>{data.candidates.map(candidate => <td key={candidate.id}>{read(candidate)}</td>)}</tr>)}</tbody></table></div></>}
  </section>;
}

export function Insights({ session, candidate, onSelect }: { session: ScreenResponse; candidate: CandidateRanking; onSelect: (id: string) => void }) {
  const [result, setResult] = useState<InsightsResponse>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const controller = useRef<AbortController>();
  useEffect(() => () => controller.current?.abort(), []);
  const analysis = result?.analysis;

  async function run() {
    const active = new AbortController();
    controller.current?.abort();
    controller.current = active;
    setResult(undefined); setError(''); setBusy(true);
    try {
      const response = await getInsights({
        job_text: session.job.raw_text, candidate_name: 'Candidate', candidate_text: candidate.resume_snippet,
        matched_skills: candidate.matched_skills, missing_skills: candidate.missing_required_skills,
      }, active.signal);
      if (!active.signal.aborted) setResult(response);
    } catch (cause) {
      if (!active.signal.aborted) setError((cause as Error).message);
    } finally {
      if (!active.signal.aborted) setBusy(false);
    }
  }

  return <div className="stack">
    <section className="panel stack"><div className="panel-heading"><label>Candidate<select value={candidateId(candidate)} onChange={event => onSelect(event.target.value)}>{session.rankings.map(item => <option key={candidateId(item)} value={candidateId(item)}>{item.candidate}</option>)}</select></label><button className="button primary" disabled={busy} onClick={run}><Sparkles size={17} />{busy ? 'Generating insights…' : error || (result && !analysis) ? 'Retry insights' : 'Generate insights'}</button></div>
    <p className="muted">This sends job information and extracted skills{candidate.resume_snippet ? ' plus a resume excerpt' : ''} to Google Gemini. Review all model interpretations against the resume.</p>
    {(error || result?.message) && <p className="notice danger" role="alert">{error || result?.message}</p>}</section>
    <section className="panel stack"><h2>Extracted evidence</h2><List items={candidate.matched_skills} /><h3>Required qualifications without detected evidence</h3><List items={candidate.missing_required_skills} /></section>
    {analysis && <section className="panel stack"><p className="eyebrow">GEMINI INTERPRETATION · HUMAN REVIEW REQUIRED</p><h2>{analysis.summary}</h2>{result.model && <p className="muted">Model {result.model}</p>}<div className="content-grid">{([
      ['Technical strengths', analysis.strengths], ['Experience observations', analysis.experience_observations],
      ['Qualifications to review', analysis.missing_qualifications], ['Areas to verify', analysis.areas_to_verify],
      ['Interview questions', analysis.interview_questions], ['Quotes from the submitted excerpt', analysis.supporting_quotes],
    ] as Array<[string, string[]]>).map(([title, items]) => <div key={title}><h3>{title}</h3><List items={items} /></div>)}</div></section>}
  </div>;
}

export function Reports({ session, shortlisted }: { session: ScreenResponse; shortlisted: Set<string> }) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const rankings = session.rankings.map(candidate => ({ ...candidate, resume_snippet: undefined, text_hash: undefined, shortlisted: shortlisted.has(candidateId(candidate)) }));
  async function downloadCsv() {
    setBusy(true); setError('');
    try { await exportCsv(rankings, session.job.job_title || 'HireLens screening'); }
    catch (cause) { setError((cause as Error).message); }
    finally { setBusy(false); }
  }
  function downloadJson() {
    const job = { ...session.job, raw_text: undefined, cleaned_text: undefined };
    const result = { ...session, job, rankings };
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url; anchor.download = 'hirelens-screening.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="panel stack"><h2>{session.job.job_title || 'Screening summary'}</h2><p>{session.total_candidates} ranked · {shortlisted.size} shortlisted · {session.file_errors.length} unreadable documents</p><p className="muted">Exports include match scores, component breakdowns, and shortlist status. Resume excerpts are omitted.</p><div className="action-row"><button className="button primary" disabled={busy} onClick={downloadCsv}><Download size={17} />{busy ? 'Preparing CSV…' : 'Download CSV'}</button><button className="button secondary" onClick={downloadJson}><Download size={17} /> Download JSON</button></div>{error && <p className="notice danger" role="alert">{error}</p>}</section>;
}
