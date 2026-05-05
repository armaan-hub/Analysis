import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';

describe('chat-msg CSS', () => {
  const css = readFileSync(resolve(__dirname, '../../../../index.css'), 'utf-8');

  it('chat-msg block has no max-width (AI messages fill full width)', () => {
    // Extract the first .chat-msg block (before --user variant)
    const match = css.match(/\.chat-msg\s*\{([^}]+)\}/);
    expect(match).not.toBeNull();
    expect(match![1]).not.toMatch(/max-width/);
  });

  it('chat-msg--user block still has max-width 60%', () => {
    const match = css.match(/\.chat-msg--user\s*\{([^}]+)\}/);
    expect(match).not.toBeNull();
    expect(match![1]).toMatch(/max-width:\s*60%/);
  });
});
