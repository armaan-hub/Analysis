// frontend/src/components/studios/LegalStudio/__tests__/chatRequestBody.test.ts
import { describe, it, expect } from 'vitest';

/**
 * Pure-function tests for the chat request body construction logic.
 * These mirror the logic in LegalStudio.tsx sendMessage() around line 601.
 */

function buildChatBody(
  text: string,
  conversationId: string | null,
  domain: string,
  mode: string,
  selectedDocIds: string[],
) {
  return {
    message: text,
    conversation_id: conversationId,
    stream: true,
    domain,
    mode,
    ...(selectedDocIds.length > 0 && { selected_doc_ids: selectedDocIds }),
  };
}

describe('buildChatBody', () => {
  it('includes selected_doc_ids when docs are selected', () => {
    const body = buildChatBody('test', null, 'vat', 'fast', ['doc-1', 'doc-2']);
    expect(body.selected_doc_ids).toEqual(['doc-1', 'doc-2']);
  });

  it('omits selected_doc_ids when no docs are selected', () => {
    const body = buildChatBody('test', null, 'vat', 'fast', []);
    expect('selected_doc_ids' in body).toBe(false);
  });

  it('includes conversation_id when provided', () => {
    const body = buildChatBody('test', 'conv-123', 'vat', 'fast', []);
    expect(body.conversation_id).toBe('conv-123');
  });

  it('always sets stream: true', () => {
    const body = buildChatBody('test', null, 'vat', 'fast', []);
    expect(body.stream).toBe(true);
  });
});
