import React, { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import type { CandidateRanking } from '../../types/api.ts';
import { exportCsv } from '../../services/api.ts';

interface ExportButtonProps {
  rankings: CandidateRanking[];
  jobTitle?: string;
  onToast: (msg: string, type?: 'info' | 'error' | 'success') => void;
}

export const ExportButton: React.FC<ExportButtonProps> = ({ rankings, jobTitle, onToast }) => {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!rankings || rankings.length === 0) {
      onToast('No candidates available to export', 'error');
      return;
    }

    setIsExporting(true);
    try {
      await exportCsv(rankings, jobTitle);
      onToast('CSV exported successfully!', 'success');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      onToast(msg, 'error');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={isExporting}
      className="inline-flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-sm transition disabled:opacity-50 cursor-pointer"
      title="Export rankings and score breakdown to CSV spreadsheet"
      aria-label="Export results to CSV"
    >
      {isExporting ? (
        <>
          <Loader2 className="w-3.5 h-3.5 animate-spin text-accent-500" />
          <span>Generating CSV...</span>
        </>
      ) : (
        <>
          <Download className="w-3.5 h-3.5 text-accent-500" />
          <span>Export Results (CSV)</span>
        </>
      )}
    </button>
  );
};
