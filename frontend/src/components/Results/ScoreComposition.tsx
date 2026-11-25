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
  const renderBarLabel = (fill: string) => (props: { x?: number; y?: number; width?: number; height?: number; value?: number }): React.ReactElement<SVGElement> => {
    const { x = 0, y = 0, width, height = 0, value } = props;
    if (!value || typeof width !== 'number' || width < 28) {
      return <g />;
    }
    return (
      <text
        x={x + width / 2}
        y={y + height / 2}
        fill={fill}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={10}
        fontWeight={700}
        style={{ pointerEvents: 'none' }}
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
      className="bg-theme-surface border border-theme-border rounded-2xl p-6 shadow-card transition-colors"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-theme-border/80 mb-5 gap-2">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-lg bg-theme-tint/60 text-theme-primary flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-theme-ink uppercase tracking-wider">
              Score Composition & Weighted Contribution
            </h3>
            <p className="text-xs text-theme-secondary-text">
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
              cursor={{ fill: 'var(--color-accent-subtle)' }}
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const data = payload[0].payload;
                  const isReqNA = nonApplicableComponents.includes('required');
                  const isPrefNA = nonApplicableComponents.includes('preferred');
                  const isExpNA = nonApplicableComponents.includes('experience');

                  return (
                    <div className="bg-theme-subtle border border-theme-border p-3.5 rounded-xl shadow-xl text-xs space-y-1.5 z-50">
                      <p className="font-bold text-theme-ink border-b border-theme-border pb-1">
                        {label}
                      </p>
                      <div className="space-y-1 text-theme-secondary-text">
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
                      <div className="pt-1.5 border-t border-theme-border flex justify-between font-bold text-theme-ink">
                        <span>Total Score:</span>
                        <span className="font-mono text-theme-primary">
                          {formatPercent(data.composite, 1)}
                        </span>
                      </div>
                      {data.belowMinExp && (
                        <div className="text-[11px] text-theme-hover font-medium pt-1">
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
                <span className="text-xs font-medium text-theme-secondary-text">
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
              label={renderBarLabel('var(--text-on-accent)')}
            />
            <Bar
              dataKey="preferred"
              name="Preferred Skills"
              stackId="a"
              fill={chartPalette.preferred}
              radius={[0, 0, 0, 0]}
              label={renderBarLabel('var(--text-on-accent)')}
            />
            <Bar
              dataKey="semantic"
              name="Semantic Match"
              stackId="a"
              fill={chartPalette.semantic}
              radius={[0, 0, 0, 0]}
              label={renderBarLabel('var(--text-on-accent)')}
            />
            <Bar
              dataKey="experience"
              name="Experience Match"
              stackId="a"
              fill={chartPalette.experience}
              radius={[0, 4, 4, 0]}
              label={renderBarLabel('var(--text-primary)')}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Minimum Experience Penalty Note */}
      {penalizedCandidates.length > 0 && (
        <div className="mt-4 p-3 bg-theme-secondary/20 border border-theme-secondary/40 rounded-xl flex items-start space-x-2 text-xs text-theme-hover">
          <AlertTriangle className="w-4 h-4 text-theme-hover flex-shrink-0 mt-0.5" />
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
