import { describe, it, expect } from 'vitest';
import { isSubstantiveAnswer } from '../isSubstantiveAnswer';

describe('isSubstantiveAnswer', () => {
  it('returns false for empty content', () => {
    expect(isSubstantiveAnswer('', [{ filename: 'x' } as any])).toBe(false);
  });

  it('returns false when sources array is empty', () => {
    expect(isSubstantiveAnswer('Here is a real answer.', [])).toBe(false);
  });

  it('returns false when content contains a non-answer phrase', () => {
    expect(isSubstantiveAnswer("I don't know the answer.", [{ filename: 'x' } as any])).toBe(false);
    expect(isSubstantiveAnswer("I couldn't find relevant info.", [{ filename: 'x' } as any])).toBe(false);
    expect(isSubstantiveAnswer("No relevant information.", [{ filename: 'x' } as any])).toBe(false);
  });

  it('returns true for a real answer with sources', () => {
    expect(
      isSubstantiveAnswer('UAE VAT standard rate is 5%.', [{ filename: 'x' } as any]),
    ).toBe(true);
  });
});
