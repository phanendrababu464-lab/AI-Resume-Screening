import { expect, test } from '@playwright/test';

test('screens real PDF and DOCX resumes, compares candidates and exports results', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Review', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Review before deciding' }).first()).toBeVisible();
  await page.getByRole('link', { name: 'Start screening' }).first().click();
  await page.getByLabel('Job description', { exact: true }).fill('Build Python and FastAPI APIs. PostgreSQL experience required.');
  await page.getByLabel('Job title').fill('Backend API engineer');
  await page.getByLabel('Required skills').fill('Python, FastAPI, PostgreSQL');
  await page.getByLabel('Upload resumes').setInputFiles(['../data/resumes/resume_01.pdf', '../data/resumes/resume_06.docx']);
  await page.getByRole('button', { name: 'Screen and rank' }).click();
  await expect(page.getByRole('heading', { name: 'Backend API engineer' })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole('row')).toHaveCount(3);
  await page.getByRole('button', { name: 'Shortlist Candidate 1' }).click();
  await page.getByLabel('Screening status').selectOption('shortlisted');
  await expect(page.getByRole('row')).toHaveCount(2);
  await page.getByLabel('Screening status').selectOption('all');
  await page.getByLabel('Search candidates').fill('Candidate 2');
  await expect(page.getByRole('row')).toHaveCount(2);
  await page.getByLabel('Search candidates').clear();
  await page.getByRole('button', { name: 'Overall' }).click();
  await expect(page.getByRole('columnheader', { name: /Overall/ })).toHaveAttribute('aria-sort', 'descending');
  await page.getByRole('link', { name: 'View Candidate 1' }).click();
  await expect(page.getByRole('heading', { name: 'Evidence and qualifications' })).toBeVisible();
  await page.getByRole('link', { name: 'AI insights' }).last().click();
  await page.getByRole('button', { name: 'Generate insights' }).click();
  await expect(page.getByRole('alert')).toContainText('unavailable');
  await page.getByRole('link', { name: 'Candidates', exact: true }).click();
  await page.getByLabel('Compare Candidate 1').check();
  await page.getByLabel('Compare Candidate 2').check();
  await page.getByRole('link', { name: 'Compare (2)' }).click();
  await expect(page.getByText('Required skills coverage')).toBeVisible();
  await page.getByRole('link', { name: 'Reports', exact: true }).click();
  for (const type of ['CSV', 'JSON']) {
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: `Download ${type}` }).click()]);
    expect(download.suggestedFilename()).toMatch(new RegExp(`[.]${type.toLowerCase()}$`));
  }
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Score distribution' })).toBeVisible();
  await expect(page.getByRole('img', { name: /0–19:/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile navigation, persistent themes, and sample recovery', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/workspace/new');
  await expect(page.getByRole('button', { name: 'Screen and rank' })).toBeDisabled();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: 'Dark', exact: true }).click();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await page.getByRole('button', { name: 'Studio', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-preset', 'studio');
  await page.getByRole('button', { name: 'Light', exact: true }).click();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'New screening', exact: true }).click();
  await page.getByRole('button', { name: 'Use sample batch' }).click();
  await expect(page.getByText('Synthetic resume batch')).toBeVisible();
  await page.getByRole('button', { name: 'Remove sample resumes' }).click();
  await expect(page.getByRole('button', { name: 'Screen and rank' })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
