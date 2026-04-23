import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Message, ResearchMessage, Source, TextMessage } from '../../../lib/api';
import { ChatMessageActions } from '../../ChatMessageActions';
import { SourcesChip } from './SourcesChip';
import { ResearchBubble } from './ResearchBubble';
import { useDocumentResolver, type SourceDocLike } from '../../../hooks/useDocumentResolver';
import { isSubstantiveAnswer } from './isSubstantiveAnswer';

interface Props {
  messages: Message[];
  loading: boolean;
  webSearching?: boolean;
  onSourceClick: (source: Source) => void;
  activeSourceId?: string;
  docs?: SourceDocLike[];
}

const SUGGESTIONS = [
  'What are the UAE VAT filing requirements?',
  'Explain IFRS 15 revenue recognition',
  'What is the Corporate Tax rate in UAE?',
  'Key differences between IFRS and US GAAP',
];

function DiamondIcon() {
  return (
    <svg className="chat-ai-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2L2 12l10 10 10-10L12 2z"/>
    </svg>
  );
}

function parseThinking(text: string): { thinking: string; answer: string } | null {
  const thinkMatch = text.match(/^<think(?:ing)?>([\s\S]*?)<\/think(?:ing)?>([\s\S]*)$/i);
  if (thinkMatch) {
    return { thinking: thinkMatch[1].trim(), answer: thinkMatch[2].trim() };
  }
  return null;
}

import { normalizeMarkdown } from '../../../lib/utils/normalizeMarkdown';

function SearchIndicator({ queries }: { queries: string[] }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{ marginBottom: '6px' }}>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '11px',
          color: 'var(--s-text-2)',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          padding: 0,
        }}
      >
        🔍 Searched the web {expanded ? '▲' : '▸'}
      </button>
      {expanded && (
        <div style={{ marginTop: '4px', paddingLeft: '16px', fontSize: '11px', color: 'var(--s-text-2)', opacity: 0.7 }}>
          {queries.map((q, i) => (
            <div key={i} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>"{q}"</div>
          ))}
        </div>
      )}
    </div>
  );
}

function AIMessage({ msg, onSourceClick, resolve }: { msg: Message; onSourceClick: (s: Source) => void; activeSourceId?: string; resolve: (path: string) => string }) {
  // Type narrow to TextMessage since this only handles AI/assistant messages
  if (msg.role === 'research') return null;
  
  const [showThinking, setShowThinking] = useState(false);
  const parsed = parseThinking(msg.text || '');
  const displayText = parsed ? parsed.answer : (msg.text || ' ');

  return (
    <div className="chat-msg chat-msg--ai">
      <DiamondIcon />
      <div className="chat-msg__body">
        <div className="chat-msg__bubble">
          {msg.queriesRun && msg.queriesRun.length > 0 && (
            <SearchIndicator queries={msg.queriesRun} />
          )}
          {parsed && (
            <>
              <button type="button" className="chat-thinking-toggle" onClick={() => setShowThinking(v => !v)}>
                <span>◆</span> Show thinking {showThinking ? '▲' : '▾'}
              </button>
              {showThinking && (
                <div className="chat-thinking-content">{parsed.thinking}</div>
              )}
            </>
          )}
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(displayText)}</ReactMarkdown>
        </div>
        {msg.sources && msg.sources.length > 0 && isSubstantiveAnswer(msg.text || '', msg.sources) && (
          <SourcesChip sources={msg.sources} onSourceClick={onSourceClick} resolveName={resolve} />
        )}
        {msg.messageId && (
          <ChatMessageActions
            messageId={msg.messageId}
            content={msg.text || ''}
            hasTable={(msg.text || '').includes('|---|') || (msg.text || '').includes('| ---')}
          />
        )}
      </div>
    </div>
  );
}

export function ChatMessages({ messages, loading, webSearching, onSourceClick, activeSourceId, docs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { resolve } = useDocumentResolver(docs);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const title = messages.find((m): m is TextMessage => m.role === 'user')?.text;

  if (messages.length === 0 && !loading) {
    return (
      <div className="chat-messages-list">
        <div className="chat-empty">
          <div className="chat-empty__glyph">⚖</div>
          <p className="chat-empty__title">Compliance & Finance Studio</p>
          <p className="chat-empty__sub">
            Ask about UAE law, tax, IFRS, audit, or financial compliance
          </p>
          <div className="chat-suggestions-grid">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                type="button"
                className="chat-suggestion-chip"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('studio:suggest', { detail: s }));
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div ref={bottomRef} />
      </div>
    );
  }

  return (
    <div className="chat-messages-list">
      {title && (
        <div style={{
          textAlign: 'center',
          fontFamily: 'var(--s-font-display)',
          fontSize: '15px',
          fontWeight: 600,
          color: 'var(--s-text-2)',
          padding: '0 0 8px',
          borderBottom: '1px solid var(--s-border)',
          marginBottom: '8px',
        }}>
          {title.length > 80 ? title.slice(0, 80) + '…' : title}
        </div>
      )}
      {messages.map((msg, i) => {
        if (msg.role === 'research') {
          const rm = msg as ResearchMessage;
          return (
            <div key={rm.id || `msg-${i}`} className="legal-section-pad">
              <ResearchBubble
                phases={rm.phases}
                report={rm.report}
                sources={rm.sources}
                query={rm.query}
                onSourceClick={onSourceClick}
              />
            </div>
          );
        }
        if (msg.role === 'user') {
          return (
            <div key={msg.id || `msg-${i}`} className="chat-msg chat-msg--user">
              <div className="chat-msg__body">
                <div className="chat-msg__bubble">
                  <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
                </div>
              </div>
            </div>
          );
        }
        return (
          <AIMessage
            key={msg.id || `msg-${i}`}
            msg={msg}
            onSourceClick={onSourceClick}
            activeSourceId={activeSourceId}
            resolve={resolve}
          />
        );
      })}
      {loading && (
        <div className="chat-msg chat-msg--ai">
          <DiamondIcon />
          <div className="chat-msg__body">
            <div className="chat-msg__bubble">
              {webSearching ? (
                <span style={{ fontFamily: 'var(--s-font-ui)', fontSize: '12px', color: 'var(--s-text-2)' }}>
                  🌐 Searching the web…
                </span>
              ) : (
                <span className="chat-typing"><span /><span /><span /></span>
              )}
            </div>
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
