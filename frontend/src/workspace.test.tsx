// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { App } from './App';
import { ThemeProvider } from './context/ThemeContext';
import * as api from './services/api';

vi.mock('./services/api', { spy: true });

beforeEach(() => {
  window.localStorage.clear();
  window.scrollTo = vi.fn();
  vi.mocked(api.serviceStatus).mockResolvedValue('ready');
  vi.mocked(api.readConfig).mockResolvedValue({ max_resumes_per_batch: 25, max_batch_size_bytes: 25 * 1024 ** 2, max_file_size_bytes: 5 * 1024 ** 2, gemini_available: false });
  vi.mocked(api.readModelInfo).mockResolvedValue({ embedding: 'MiniLM', skills: 'spaCy', keyword: 'TF-IDF', gemini: 'Gemini' });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

function visit(path: string) {
  render(<ThemeProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></ThemeProvider>);
  return userEvent.setup();
}

test('landing preview and workspace navigation use accessible controls', async () => {
  const user = visit('/');
  await user.click(screen.getByRole('button', { name: /^Upload$/ }));
  expect(screen.getAllByRole('heading', { name: 'Set the role criteria' })).toHaveLength(2);
  await user.click(screen.getByRole('link', { name: 'Open workspace' }));
  expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeTruthy();
});

test('validates input and retains uploads when screening fails', async () => {
  const user = visit('/workspace/new');
  vi.mocked(api.screenResumes).mockRejectedValueOnce(new Error('The backend is busy.'));
  const upload = screen.getByLabelText('Upload resumes');
  const run = screen.getByRole('button', { name: 'Screen and rank' }) as HTMLButtonElement;
  expect(run.disabled).toBe(true);
  await user.type(screen.getByRole('textbox', { name: 'Job description' }), 'Python engineer');
  await user.upload(upload, new File(['%PDF-test'], 'candidate.pdf', { type: 'application/pdf' }));
  expect(run.disabled).toBe(false);
  await user.click(run);
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'The backend is busy.');
  expect(screen.getByText('candidate.pdf')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Retry screening' })).toBeTruthy();
});

test('recovers readiness on request and saves theme choice', async () => {
  vi.mocked(api.serviceStatus).mockRejectedValueOnce(new Error('Connection refused'));
  const user = visit('/workspace/status');
  expect(await screen.findByRole('heading', { name: 'Backend unavailable' })).toBeTruthy();
  await user.click(screen.getByRole('button', { name: 'Check again' }));
  expect(await screen.findByRole('heading', { name: 'All systems operational' })).toBeTruthy();
  await user.click(screen.getByRole('link', { name: 'Settings' }));
  await user.click(screen.getByRole('button', { name: 'Dark' }));
  await waitFor(() => expect(document.documentElement.classList.contains('dark')).toBe(true));
});
