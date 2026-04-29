import { describe, it, expect } from 'vitest';
import { normalizeMarkdown } from '../../../../lib/utils/normalizeMarkdown';

describe('normalizeMarkdown', () => {
  it('adds blank line before ## header when preceded by a non-blank line', () => {
    const result = normalizeMarkdown('Some text\n## Section Title\nMore text');
    expect(result).toMatch(/Some text\n\n## Section Title/);
  });

  it('does not triple-up blank lines when blank line already present', () => {
    const input = 'Some text\n\n## Section Title\nMore text';
    const result = normalizeMarkdown(input);
    expect(result).toBe(input);           // idempotent: already correct, no change
    expect(result).not.toMatch(/\n\n\n/); // belt-and-suspenders
  });

  it('adds blank lines around --- divider with no surrounding blank lines', () => {
    const result = normalizeMarkdown('First paragraph\n---\nSecond paragraph');
    expect(result).toMatch(/First paragraph\n\n---/);
    expect(result).toMatch(/---\n\nSecond paragraph/);
  });

  it('leaves plain text unchanged', () => {
    const input = 'Hello world\nThis is a normal message.';
    expect(normalizeMarkdown(input)).toBe(input);
  });

  it('collapses double-prefixed LLM headers: ### ## Foo → ## Foo', () => {
    const result = normalizeMarkdown('### ## What is E-Invoicing\nSome text');
    expect(result).toMatch(/^## What is E-Invoicing/m);
    expect(result).not.toMatch(/### ##/);
  });

  it('collapses triple-prefixed LLM headers: #### ### Bar → ### Bar', () => {
    const result = normalizeMarkdown('#### ### E-Invoicing Phases\nSome text');
    expect(result).toMatch(/^### E-Invoicing Phases/m);
    expect(result).not.toMatch(/#### ###/);
  });

  it('collapses deep double-prefix: ##### #### 3.1 → #### 3.1', () => {
    const result = normalizeMarkdown('##### #### 3.1: Update Tally\nSome text');
    expect(result).toMatch(/^#### 3\.1: Update Tally/m);
    expect(result).not.toMatch(/##### ####/);
  });

  it('leaves correctly formed single-prefix headers unchanged', () => {
    const input = '## Section\n### Sub-section\n#### Deep';
    const result = normalizeMarkdown(input);
    expect(result).toMatch(/## Section/);
    expect(result).toMatch(/### Sub-section/);
    expect(result).toMatch(/#### Deep/);
  });

  it('adds blank line before pipe-table following non-empty text', () => {
    const result = normalizeMarkdown('Intro text\n| A | B |\n|---|---|\n| 1 | 2 |');
    expect(result).toMatch(/Intro text\n\n\| A \| B \|/);
  });

  it('does NOT inject blank lines between table rows', () => {
    const input = '| Header | Value |\n|---|---|\n| Row 1 | data |\n| Row 2 | data |';
    const result = normalizeMarkdown(input);
    // All rows must stay contiguous — no \n\n between pipe rows
    expect(result).not.toMatch(/\|[^\n]*\n\n\|/);
  });

  it('does NOT inject blank line between header and separator row', () => {
    const input = 'Some text\n| A | B |\n|---|---|\n| x | y |';
    const result = normalizeMarkdown(input);
    // Separator row must immediately follow header row
    expect(result).toMatch(/\| A \| B \|\n\|---\|---\|/);
  });

  it('collapses LLM-emitted blank lines between table rows', () => {
    // LLMs often emit \n\n between header, separator, and body rows
    const input = '### Tax Treatment\n| Type | Rate |\n\n|---|---|\n\n| Exempt | 0% |\n\n| Taxable | 9% |';
    const result = normalizeMarkdown(input);
    expect(result).not.toMatch(/\|[^\n]*\n\n\|/);
    // Table rows stay together
    expect(result).toMatch(/\| Type \| Rate \|\n\|---\|---\|\n\| Exempt \| 0% \|\n\| Taxable \| 9% \|/);
  });
});
