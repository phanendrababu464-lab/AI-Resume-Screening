import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { CandidateRanking, ComparisonResult } from '../types/api';

const chartTooltipStyle = { background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--ink)' };

export function Distribution({ rankings }: { rankings: CandidateRanking[] }) {
  const ranges = ['0–19', '20–39', '40–59', '60–79', '80–100'];
  const data = ranges.map((range, index) => ({
    range,
    candidates: rankings.filter(candidate => Math.min(4, Math.floor(candidate.match_score / 20)) === index).length,
  }));
  return <div className="chart" role="img" aria-label={data.map(item => `${item.range}: ${item.candidates} candidates`).join(', ')}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ left: -22, right: 10, top: 16 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="4 4" />
        <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 12 }} />
        <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: 'var(--muted)', fontSize: 12 }} />
        <Tooltip cursor={{ fill: 'var(--tone)' }} contentStyle={chartTooltipStyle} />
        <Bar dataKey="candidates" name="Candidates" fill="var(--accent)" radius={[6, 6, 0, 0]} maxBarSize={47} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}

export function ComparisonChart({ candidates }: ComparisonResult) {
  const data = candidates.map(candidate => ({ label: candidate.label, match: candidate.overall }));
  return <div className="chart" role="img" aria-label={data.map(item => `${item.label}: ${item.match}%`).join(', ')}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ left: -22, right: 10, top: 16 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" />
        <XAxis dataKey="label" hide />
        <YAxis domain={[0, 100]} tick={{ fill: 'var(--muted)', fontSize: 12 }} />
        <Tooltip cursor={{ fill: 'var(--chart-comparison-cursor)' }} contentStyle={chartTooltipStyle} />
        <Bar dataKey="match" name="Overall match" fill="var(--accent)" radius={[6, 6, 0, 0]} maxBarSize={65} />
      </BarChart>
    </ResponsiveContainer>
  </div>;
}
