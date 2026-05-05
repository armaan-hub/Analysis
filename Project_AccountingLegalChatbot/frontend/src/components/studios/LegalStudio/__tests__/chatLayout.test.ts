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

  it('user bubble still has max-width constraint', () => {
    // The effective user-bubble constraint is on .chat-msg--user .chat-msg__bubble
    const bubbleMatches = Array.from(
      css.matchAll(/\.chat-msg--user\s+\.chat-msg__bubble\s*\{([^}]+)\}/g),
    );
    if (bubbleMatches.length > 0) {
      const hasMaxWidth = bubbleMatches.some((match) => /max-width/.test(match[1]));
      expect(hasMaxWidth).toBe(true);
      return;
    }

    const userMatch = css.match(/\.chat-msg--user\s*\{([^}]+)\}/);
    expect(userMatch).not.toBeNull();
    expect(userMatch![1]).toMatch(/max-width/);
  });

  it('AI bubble has width: 100%', () => {
    const match = css.match(/\.chat-msg--ai\s+\.chat-msg__bubble\s*\{([^}]+)\}/);
    expect(match).not.toBeNull();
    expect(match![1]).toMatch(/width:\s*100%/);
  });
});
