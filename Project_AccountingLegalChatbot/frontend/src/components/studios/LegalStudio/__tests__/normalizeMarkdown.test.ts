import { describe, it, expect } from 'vitest';
import { normalizeMarkdown } from '../ChatMessages';

describe('normalizeMarkdown', () => {
  it('adds blank line before ## header when preceded by a non-blank line', () => {
    const result = normalizeMarkdown('Some text\n## Section Title\nMore text');
    expect(result).toMatch(/Some text\n\n## Section Title/);
  });

  it('does not triple-up blank lines when blank line already present', () => {
    const result = normalizeMarkdown('Some text\n\n## Section Title\nMore text');
    expect(result).not.toMatch(/\n\n\n/);
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
});
