import React from 'react';
import { Layers, AlertTriangle } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts';
import type { ScoreCompositionItem, CandidateRanking } from '../../types/api.ts';
import { formatPercent } from '../../utils/helpers.ts';
import { useTheme } from '../../context/ThemeContext.tsx';

interface ScoreCompositionProps {
  compositionData: ScoreCompositionItem[];
  rankings: CandidateRanking[];
  nonApplicableComponents?: string[];
}

export const ScoreComposition: React.FC<ScoreCompositionProps> = ({
  compositionData,
  rankings,
  nonApplicableComponents = [],
}) => {
  const { chartPalette } = useTheme();

  // Custom label renderer showing percentage on stacked bars when width >= 28px
  const renderBarLabel = (props: any): React.ReactElement<SVGElement> => {
    const { x, y, width, height, value } = props;
    if (!value || typeof width !== 'number' || width < 28) {
      return <g />;
    }
    return (
      <text
        x={x + width / 2}
        y={y + height / 2}
        fill="#ffffff"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={10}
        fontWeight={700}
        style={{ pointerEvents: 'none', textShadow: '0 1px 2px rgba(0,0,0,0.6)' }}
      >
        {Math.round(value)}%
      </text>
    );
  };

  // Transform flat backend ScoreCompositionItem rows into Recharts candidate-keyed objects
  const candidateMap: Record<
    string,
    {
      name: string;
      required: number;
      preferred: number;
      semantic: number;
      experience: number;
      composite: number;
      belowMinExp: boolean;
      penaltyNote: string;
    }
  > = {};

  for (const item of compositionData) {
    if (!candidateMap[item.candidate]) {
      const matchCandidate = rankings.find((r) => r.candidate === item.candidate);
      candidateMap[item.candidate] = {
        name: item.candidate,
        required: 0,
        preferred: 0,
        semantic: 0,
        experience: 0,
        composite: matchCandidate ? matchCandidate.match_score : 0,
        belowMinExp: item.below_min_experience,
        penaltyNote: item.penalty_note || '',
      };
    }

    const val = item.contribution || 0;
    if (item.component.includes('Required')) {
      candidateMap[item.candidate].required = val;
    } else if (item.component.includes('Preferred')) {
      candidateMap[item.candidate].preferred = val;
    } else if (item.component.includes('Semantic')) {
      candidateMap[item.candidate].semantic = val;
    } else if (item.component.includes('Experience')) {
      candidateMap[item.candidate].experience = val;
    }
  }

  // Preserve rank order from rankings
  const chartData = rankings
    .map((r) => candidateMap[r.candidate])
    .filter(Boolean);

  // Penalized candidates list for explanatory note
  const penalizedCandidates = rankings.filter((r) => r.below_min_experience);

  return (
    <div
      id="results-composition"
      className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-card transition-colors"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800/80 mb-5 gap-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-accent-50 text-accent-600 dark:bg-accent-950/60 dark:text-accent-400 flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Score Composition & Weighted Contribution
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Stacked points sum exactly to candidate's composite match score
            </p>
          </div>
        </div>
      </div>

      {/* Recharts Stacked Horizontal Bar Chart with Dynamic Accessible Palette */}
      <div className="w-full h-80 sm:h-96">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 10, right: 30, left: 10, bottom: 20 }}
          >
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fill: chartPalette.text, fontSize: 11 }}
              tickFormatter={(val) => `${val}%`}
              stroke={chartPalette.grid}
            />
            <YAxis
              dataKey="name"
              type="category"
              width={120}
              tick={{ fill: chartPalette.text, fontSize: 12, fontWeight: 500 }}
              stroke={chartPalette.grid}
              tickFormatter={(val) => (val.length > 14 ? `${val.slice(0, 12)}…` : val)}
            />
            <Tooltip
              cursor={{ fill: 'rgba(128, 128, 128, 0.08)' }}
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  const isReqNA = nonApplicableComponents.includes('required');
                  const isPrefNA = nonApplicableComponents.includes('preferred');
                  const isExpNA = nonApplicableComponents.includes('experience');

                  return (
                    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-3.5 rounded-xl shadow-xl text-xs space-y-1.5 z-50">
                      <p className="font-bold text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 pb-1">
                        {label}
                      </p>
                      <div className="space-y-1 text-slate-600 dark:text-slate-300">
                        <div className="flex justify-between gap-4">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-sm"
                              style={{ backgroundColor: chartPalette.required }}
                            />
                            Required Skills:
                          </span>
                          <span className="font-mono font-semibold">
                            {isReqNA ? 'N/A' : formatPercent(data.required, 1)}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-sm"
                              style={{ backgroundColor: chartPalette.preferred }}
                            />
                            Preferred Skills:
                          </span>
                          <span className="font-mono font-semibold">
                            {isPrefNA ? 'N/A' : formatPercent(data.preferred, 1)}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-sm"
                              style={{ backgroundColor: chartPalette.semantic }}
                            />
                            Semantic Similarity:
                          </span>
                          <span className="font-mono font-semibold">
                            {formatPercent(data.semantic, 1)}
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="flex items-center gap-1.5">
                            <span
                              className="w-2.5 h-2.5 rounded-sm"
                              style={{ backgroundColor: chartPalette.experience }}
                            />
                            Experience Match:
                          </span>
                          <span className="font-mono font-semibold">
                            {isExpNA ? 'N/A' : formatPercent(data.experience, 1)}
                          </span>
                        </div>
                      </div>
                      <div className="pt-1.5 border-t border-slate-100 dark:border-slate-700 flex justify-between font-bold text-slate-900 dark:text-slate-100">
                        <span>Total Score:</span>
                        <span className="font-mono text-accent-600 dark:text-accent-400">
                          {formatPercent(data.composite, 1)}
                        </span>
                      </div>
                      {data.belowMinExp && (
                        <div className="text-[11px] text-amber-600 dark:text-amber-400 font-medium pt-1">
                          ⚠️ Below minimum experience{data.penaltyNote}
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              wrapperStyle={{ paddingTop: 10 }}
              formatter={(value) => (
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  {value}
                </span>
              )}
            />
            <Bar
              dataKey="required"
              name="Required Skills"
              stackId="a"
              fill={chartPalette.required}
              radius={[0, 0, 0, 0]}
              label={renderBarLabel}
            />
            <Bar
              dataKey="preferred"
              name="Preferred Skills"
              stackId="a"
              fill={chartPalette.preferred}
              radius={[0, 0, 0, 0]}
              label={renderBarLabel}
            />
            <Bar
              dataKey="semantic"
              name="Semantic Match"
              stackId="a"
              fill={chartPalette.semantic}
              radius={[0, 0, 0, 0]}
              label={renderBarLabel}
            />
            <Bar
              dataKey="experience"
              name="Experience Match"
              stackId="a"
              fill={chartPalette.experience}
              radius={[0, 4, 4, 0]}
              label={renderBarLabel}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Minimum Experience Penalty Note */}
      {penalizedCandidates.length > 0 && (
        <div className="mt-4 p-3 bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/80 dark:border-amber-900/40 rounded-xl flex items-start space-x-2 text-xs text-amber-800 dark:text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Minimum-Experience Penalty Applied: </span>
            {penalizedCandidates.map((c) => (
              <span key={c.candidate} className="font-mono font-semibold mr-1.5">
                `{c.candidate}`
              </span>
            ))}
            fell below the target job's minimum experience threshold. Each component contribution is scaled by the applied penalty multiplier.
          </div>
        </div>
      )}
    </div>
  );
};
