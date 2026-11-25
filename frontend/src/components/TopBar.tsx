import React, { useEffect, useRef, useState } from 'react';
import {
  Sparkles,
  Sun,
  Moon,
  HelpCircle,
  Palette,
  Minimize2,
  LayoutDashboard,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext.tsx';
import type { Preset } from '../tokens/presets.ts';
import { checkHealth } from '../services/api.ts';

interface TopBarProps {
  onOpenExplainer: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenExplainer }) => {
  const { theme, toggleTheme, preset, setPreset } = useTheme();
  const [isApiHealthy, setIsApiHealthy] = useState<boolean | null>(null);
  const isCheckingRef = useRef(false);

  useEffect(() => {
    let isMounted = true;
    const verifyApi = async () => {
      if (isCheckingRef.current) return;
      isCheckingRef.current = true;
      try {
        await checkHealth();
        if (isMounted) setIsApiHealthy(true);
      } catch {
        if (isMounted) setIsApiHealthy(false);
      } finally {
        isCheckingRef.current = false;
      }
    };

    verifyApi();
    const interval = setInterval(verifyApi, 25000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const presetOptions: { id: Preset; label: string; icon: typeof Palette; desc: string }[] = [
    {
      id: 'studio',
      label: 'Studio',
      icon: Palette,
      desc: 'Refined editorial style with indigo accent and soft elevation',
    },
    {
      id: 'minimal',
      label: 'Minimal',
      icon: Minimize2,
      desc: 'Calm, print-like monochrome with hairline borders and zero shadows',
    },
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      desc: 'Data-dense analytics with compact spacing, slim sidebar, and KPI tiles',
    },
  ];

  return (
    <header className="relative z-40 border-b border-slate-200 dark:border-midnight-border bg-white dark:bg-midnight-surface transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2 sm:gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="w-10 h-10 rounded-xl bg-accent-600 dark:bg-midnight-primary text-white dark:text-midnight-on-accent flex items-center justify-center shadow-md shadow-accent-500/20 dark:shadow-midnight-primary/20">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 dark:text-midnight-ink tracking-tight leading-none">
              AI Resume Screening
            </h1>
            <p className="text-[11px] text-slate-500 dark:text-midnight-muted mt-1 hidden sm:block">
              Deterministic NLP & Semantic Evaluation
            </p>
          </div>
        </div>

        {/* Center / Right Controls: Style Presets, API Status, Explainer, Theme Toggle */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Style Presets Switcher */}
          <div
            className="flex items-center p-0.5 rounded-lg bg-slate-100 dark:bg-midnight-border border border-slate-200 dark:border-midnight-border"
            role="radiogroup"
            aria-label="Visual style presets"
          >
            {presetOptions.map((opt) => {
              const Icon = opt.icon;
              const isSelected = preset === opt.id;
              return (
                <button
                  key={opt.id}
                  data-preset-btn={opt.id}
                  onClick={() => setPreset(opt.id)}
                  role="radio"
                  aria-checked={isSelected}
                  title={opt.desc}
                  className={`flex items-center space-x-1.5 px-2 sm:px-2.5 py-1 text-xs font-medium rounded-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:focus-visible:ring-midnight-primary ${
                    isSelected
                      ? 'bg-white dark:bg-midnight-surface text-slate-900 dark:text-midnight-ink shadow-sm font-semibold'
                      : 'text-slate-600 dark:text-midnight-muted hover:text-slate-900 dark:hover:text-midnight-hover'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="hidden md:inline">{opt.label}</span>
                </button>
              );
            })}
          </div>

          {/* API Status Indicator */}
          <div
            className={`hidden lg:inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
              isApiHealthy === true
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-midnight-tint/40 dark:text-midnight-ink dark:border-midnight-border'
                : isApiHealthy === false
                ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-midnight-secondary/40 dark:text-midnight-hover dark:border-midnight-secondary'
                : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-midnight-border dark:text-midnight-muted dark:border-midnight-border'
            }`}
            title={isApiHealthy ? 'Backend API is online and responding' : 'Backend API is unreachable on :8000'}
            aria-label="API status indicator"
          >
            {isApiHealthy === true ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-500 dark:bg-midnight-ink animate-pulse" />
                <span>API Online</span>
              </>
            ) : isApiHealthy === false ? (
              <>
                <span className="w-2 h-2 rounded-full bg-rose-500 dark:bg-midnight-hover" />
                <span>API Offline</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-slate-400 dark:bg-midnight-muted" />
                <span>Checking API...</span>
              </>
            )}
          </div>

          {/* How Scoring Works button */}
          <button
            onClick={onOpenExplainer}
            className="hidden sm:inline-flex items-center space-x-1.5 px-2.5 sm:px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 dark:text-midnight-muted hover:bg-slate-100 dark:hover:bg-midnight-tint border border-slate-200 dark:border-midnight-border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:focus-visible:ring-midnight-primary"
            aria-label="Open scoring formula explainer"
          >
            <HelpCircle className="w-3.5 h-3.5 text-slate-400 dark:text-midnight-muted" />
            <span className="hidden sm:inline">How Scoring Works</span>
          </button>

          {/* Theme Toggle Button (Separate from Preset Switcher) */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg text-slate-600 dark:text-midnight-muted hover:bg-slate-100 dark:hover:bg-midnight-tint border border-slate-200 dark:border-midnight-border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 dark:focus-visible:ring-midnight-primary"
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400 dark:text-midnight-hover" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600 dark:text-midnight-muted" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
