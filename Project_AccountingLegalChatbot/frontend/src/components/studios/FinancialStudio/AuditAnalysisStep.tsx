import { useState, useRef, useEffect } from 'react';

function DiamondIcon() {
  return (
    <svg className="chat-ai-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2L2 12l10 10 10-10L12 2z"/>
    </svg>
  );
}

interface AnalysisMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  draftContent: string;
  trialBalanceSummary: string;
  priorYearContext: string;
  companyName: string;
  periodEnd: string;
  onComplete: (analysisHistory: AnalysisMessage[]) => void;
  onBack: () => void;
}

export function AuditAnalysisStep({
  draftContent,
  trialBalanceSummary,
  priorYearContext,
  companyName,
  periodEnd,
  onComplete,
  onBack,
}: Props) {
  const [messages, setMessages] = useState<AnalysisMessage[]>([
    {
      role: 'assistant',
      content: `I've reviewed the draft audit report for ${companyName || 'this company'} for the period ending ${periodEnd || 'the current period'}. What would you like to discuss or clarify before we proceed to formatting?`,
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [draftOpen, setDraftOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: AnalysisMessage = { role: 'user', content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    const assistantMsg: AnalysisMessage = { role: 'assistant', content: '' };
    setMessages([...newMessages, assistantMsg]);

    try {
      const res = await fetch('/api/reports/analysis-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_history: messages.map(m => ({ role: m.role, content: m.content })),
          trial_balance_summary: trialBalanceSummary,
          prior_year_context: priorYearContext,
          draft_content: draftContent,
          company_name: companyName,
          period_end: periodEnd,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error('Stream failed');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event: { type: string; content?: string; message?: string };
          try {
            event = JSON.parse(raw);
          } catch {
            // Fallback: treat as raw text chunk (backward compat)
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + raw };
              return updated;
            });
            continue;
          }

          if (event.type === 'chunk' && event.content) {
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + event.content };
              return updated;
            });
          } else if (event.type === 'done') {
            break;
          } else if (event.type === 'error') {
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                content: `Error: ${event.message || 'Unknown error'}. Please try again.`,
              };
              return updated;
            });
            break;
          }
        }
      }
    } catch (err) {
      console.error('Analysis chat error:', err);
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: 'Sorry, I encountered an error. Please try again.',
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      minHeight: 0,
      fontFamily: 'var(--s-font-ui)',
    }}>
      {/* Header */}
      <div style={{ textAlign: 'center', padding: '24px 24px 12px', flexShrink: 0 }}>
        <DiamondIcon />
        <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--s-text-1)', marginTop: '8px' }}>
          Analysis &amp; Discussion
        </div>
        <div style={{ fontSize: '13px', color: 'var(--s-text-2)', marginTop: '4px' }}>
          {companyName && <span>{companyName}</span>}
          {companyName && periodEnd && <span style={{ margin: '0 6px' }}>·</span>}
          {periodEnd && <span>{periodEnd}</span>}
        </div>
      </div>

      {/* Draft toggle */}
      {draftContent && (
        <div style={{ padding: '0 24px 8px', flexShrink: 0 }}>
          <button
            onClick={() => setDraftOpen(v => !v)}
            style={{
              background: 'none',
              border: '1px solid var(--s-border)',
              borderRadius: 'var(--s-r-sm)',
              padding: '4px 10px',
              fontSize: '12px',
              color: 'var(--s-text-2)',
              cursor: 'pointer',
            }}
          >
            {draftOpen ? '▲ Hide Draft' : '▾ View Draft'}
          </button>
          {draftOpen && (
            <div style={{
              marginTop: '8px',
              padding: '12px',
              borderRadius: 'var(--s-r-md)',
              border: '1px solid var(--s-border)',
              background: 'var(--s-surface)',
              fontSize: '12px',
              color: 'var(--s-text-1)',
              maxHeight: '200px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
              lineHeight: 1.5,
            }}>
              {draftContent}
            </div>
          )}
        </div>
      )}

      {/* Suggestion chips — shown only on first turn */}
      {messages.length === 1 && !loading && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          padding: '0 24px 12px',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          {[
            'Summarise key variances from prior year',
            'What are the main risks in this audit?',
            'Explain the disclaimer of opinion',
            'Are there any going concern issues?',
          ].map(suggestion => (
            <button
              key={suggestion}
              onClick={() => { setInput(suggestion); }}
              style={{
                padding: '8px 14px',
                borderRadius: 'var(--s-r-md)',
                border: '1px solid var(--s-border)',
                background: 'var(--s-surface)',
                color: 'var(--s-text-1)',
                fontSize: '12px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'var(--s-ease)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-accent)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-accent)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--s-border)';
                (e.currentTarget as HTMLButtonElement).style.color = 'var(--s-text-1)';
              }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      {/* Chat messages */}
      <div style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: '0 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            {msg.role === 'assistant' && (
              <div style={{ flexShrink: 0, marginTop: '2px' }}>
                <DiamondIcon />
              </div>
            )}
            <div style={{
              maxWidth: '72%',
              padding: '10px 14px',
              borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
              background: msg.role === 'user' ? 'var(--s-accent)' : 'var(--s-surface)',
              color: msg.role === 'user' ? '#fff' : 'var(--s-text-1)',
              fontSize: '13px',
              lineHeight: 1.55,
              border: msg.role === 'user' ? 'none' : '1px solid var(--s-border)',
              whiteSpace: 'pre-wrap',
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ flexShrink: 0 }}>
              <DiamondIcon />
            </div>
            <div style={{
              padding: '10px 14px',
              borderRadius: '12px 12px 12px 2px',
              background: 'var(--s-surface)',
              border: '1px solid var(--s-border)',
            }}>
              <span className="chat-typing"><span /><span /><span /></span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar + nav buttons */}
      <div style={{ flexShrink: 0, padding: '12px 24px 16px', borderTop: '1px solid var(--s-border)' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the financials or draft…  (Shift+Enter for new line)"
            rows={2}
            disabled={loading}
            style={{
              flex: 1,
              resize: 'none',
              borderRadius: 'var(--s-r-md)',
              border: '1px solid var(--s-border)',
              padding: '10px 12px',
              fontSize: '13px',
              fontFamily: 'var(--s-font-ui)',
              background: 'var(--s-surface)',
              color: 'var(--s-text-1)',
              outline: 'none',
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            style={{
              padding: '0 18px',
              borderRadius: 'var(--s-r-md)',
              border: 'none',
              background: input.trim() && !loading ? 'var(--s-accent)' : 'var(--s-border)',
              color: input.trim() && !loading ? '#fff' : 'var(--s-text-2)',
              fontFamily: 'var(--s-font-ui)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: input.trim() && !loading ? 'pointer' : 'default',
              transition: 'var(--s-ease)',
              alignSelf: 'stretch',
            }}
          >
            Send
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={onBack}
            style={{
              background: 'none',
              border: '1px solid var(--s-border)',
              borderRadius: 'var(--s-r-sm)',
              padding: '6px 14px',
              fontSize: '13px',
              color: 'var(--s-text-2)',
              cursor: 'pointer',
              fontFamily: 'var(--s-font-ui)',
            }}
          >
            ← Back to Draft
          </button>
          <button
            onClick={() => onComplete(messages)}
            disabled={loading}
            style={{
              background: loading ? 'var(--s-border)' : 'var(--s-accent)',
              border: 'none',
              borderRadius: 'var(--s-r-sm)',
              padding: '6px 18px',
              fontSize: '13px',
              fontWeight: 600,
              color: loading ? 'var(--s-text-2)' : '#fff',
              cursor: loading ? 'default' : 'pointer',
              fontFamily: 'var(--s-font-ui)',
            }}
          >
            Proceed to Format Selection →
          </button>
        </div>
      </div>
    </div>
  );
}
