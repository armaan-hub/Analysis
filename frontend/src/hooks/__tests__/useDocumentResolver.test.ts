import { renderHook } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useDocumentResolver } from '../useDocumentResolver';

const docs = [
  { id: 'abc-123', filename: '4af67c70-7caf.pdf', original_name: 'Financial_Statements_2024.pdf' },
  { id: 'def-456', filename: 'b9e1.pdf',           original_name: 'Policy.pdf' },
] as any;

describe('useDocumentResolver', () => {
  it('resolves a UUID id to original_name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('abc-123')).toBe('Financial_Statements_2024.pdf');
  });

  it('resolves a stored UUID filename to original_name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('4af67c70-7caf.pdf')).toBe('Financial_Statements_2024.pdf');
  });

  it('passes through an unknown string unchanged', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('something-else.txt')).toBe('something-else.txt');
  });

  it('passes through an already-original name', () => {
    const { result } = renderHook(() => useDocumentResolver(docs));
    expect(result.current.resolve('Policy.pdf')).toBe('Policy.pdf');
  });
});
