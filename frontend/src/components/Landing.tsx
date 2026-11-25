import { Link } from 'react-router-dom';
import { ArrowUpRight, FileStack, Fingerprint, Layers3, ScanLine, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

export function Brand() {
  return <Link to="/" className="brand"><span className="brand-icon"><ScanLine size={19} /></span><span>HireLens<span className="brand-ai"> AI</span></span></Link>;
}

const stages = [
  { label: 'Upload', icon: FileStack, title: 'Set the role criteria', text: 'Add a job description and upload a batch of PDF or DOCX resumes.' },
  { label: 'Screen', icon: Layers3, title: 'See what drives each score', text: 'Inspect semantic similarity, keyword relevance, skill coverage, and experience evidence.' },
  { label: 'Review', icon: ShieldCheck, title: 'Review before deciding', text: 'Compare shortlisted candidates, examine gaps, and prepare job-specific interview questions.' },
];

export default function Landing() {
  const [stage, setStage] = useState(1);
  const selected = stages[stage];
  const PreviewIcon = selected.icon;
  return <div className="landing">
    <header className="landing-nav"><Brand /><nav aria-label="Landing"><a href="#workflow">How it works</a><a href="#privacy">Privacy</a><Link className="button primary" to="/workspace">Open workspace <ArrowUpRight size={16} /></Link></nav></header>
    <main>
      <section className="landing-hero">
        <div><p className="eyebrow">TECHNICAL RECRUITING</p><h1>See the evidence behind every match.</h1><p className="lede">Screen resumes against the role, understand what drove each ranking, and give every shortlist a human review.</p><Link className="button primary" to="/workspace/new">Start screening <ArrowUpRight size={17} /></Link></div>
        <div className="preview" aria-label="Interactive screening preview">
          <div className="preview-brand"><ScanLine size={20} /> Screening workflow</div>
          <div className="preview-tabs" aria-label="Preview stage">{stages.map((item, index) => <button key={item.label} onClick={() => setStage(index)} aria-pressed={stage === index}>{item.label}</button>)}</div>
          <div className="preview-content"><div className="feature-icon"><PreviewIcon size={25} /></div><h2>{selected.title}</h2><p>{selected.text}</p>{stage === 1 && <div className="preview-weights">{[['Semantic', 40], ['Keywords', 20], ['Skills', 30], ['Experience', 10]].map(([label, weight]) => <div key={label}><span>{label}</span><b>{weight}%</b></div>)}</div>}</div>
        </div>
      </section>
      <section id="workflow" className="landing-section"><p className="eyebrow">HOW IT WORKS</p><h2>From job description to interview.</h2><div className="landing-features">{stages.map(({ label, icon: Icon, title, text }) => <article className="panel" key={label}><div className="feature-icon"><Icon size={22} /></div><h3>{title}</h3><p>{text}</p></article>)}</div></section>
      <section id="privacy" className="landing-section privacy"><Fingerprint size={32} /><div><h2>Candidate data stays session-scoped.</h2><p>Screening results remain in the current browser tab. Gemini receives excerpts and job information only when you request AI insights. Matches are heuristic estimates for human review.</p></div><Link className="button primary" to="/workspace/new">Start screening</Link></section>
    </main>
    <footer className="landing-nav"><Brand /><span>Evidence-led technical screening</span></footer>
  </div>;
}
