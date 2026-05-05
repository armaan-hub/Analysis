import { describe, it, expect } from 'vitest';

describe('required dependencies are importable', () => {
  it('remark-math resolves', async () => {
    const mod = await import('remark-math');
    expect(mod).toBeDefined();
  });
  it('rehype-katex resolves', async () => {
    const mod = await import('rehype-katex');
    expect(mod).toBeDefined();
  });
  it('rehype-highlight resolves', async () => {
    const mod = await import('rehype-highlight');
    expect(mod).toBeDefined();
  });
  it('react-syntax-highlighter resolves', async () => {
    const mod = await import('react-syntax-highlighter');
    expect(mod).toBeDefined();
  });
});
