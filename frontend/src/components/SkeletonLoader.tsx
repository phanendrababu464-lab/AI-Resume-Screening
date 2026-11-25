import React from 'react';

export const SkeletonLoader: React.FC = () => {
  return (
    <div className="space-y-6 animate-pulse" aria-label="Loading candidate evaluation results">
      {/* Hero card skeleton */}
      <div className="bg-theme-surface border border-theme-border rounded-2xl p-7 shadow-card">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
          <div className="space-y-3 flex-1">
            <div className="w-36 h-6 bg-theme-subtle rounded-full" />
            <div className="w-64 h-8 bg-theme-subtle rounded-lg" />
            <div className="w-full max-w-lg h-16 bg-theme-subtle/60 rounded-xl" />
          </div>
          <div className="w-32 h-32 rounded-full bg-theme-subtle flex-shrink-0" />
        </div>
        <div className="mt-6 pt-5 border-t border-theme-border grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="h-20 bg-theme-subtle/50 rounded-xl" />
          <div className="h-20 bg-theme-subtle/50 rounded-xl" />
          <div className="h-20 bg-theme-subtle/50 rounded-xl" />
        </div>
      </div>

      {/* Leaderboard skeleton */}
      <div className="bg-theme-surface border border-theme-border rounded-2xl p-6 shadow-card space-y-4">
        <div className="w-48 h-6 bg-theme-subtle rounded" />
        <div className="space-y-3">
          <div className="h-16 bg-theme-subtle/50 rounded-xl" />
          <div className="h-16 bg-theme-subtle/50 rounded-xl" />
          <div className="h-16 bg-theme-subtle/50 rounded-xl" />
        </div>
      </div>
    </div>
  );
};
