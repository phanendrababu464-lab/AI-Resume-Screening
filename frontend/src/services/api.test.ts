import { afterEach, expect, it, vi } from 'vitest';
import { fetchSamples } from './api';

afterEach(() => vi.unstubAllGlobals());

it('skips the samples request when the caller already cancelled it', async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  const controller = new AbortController();
  controller.abort();

  await expect(fetchSamples(controller.signal)).rejects.toThrow('Request was cancelled');
  expect(fetchMock).not.toHaveBeenCalled();
});
