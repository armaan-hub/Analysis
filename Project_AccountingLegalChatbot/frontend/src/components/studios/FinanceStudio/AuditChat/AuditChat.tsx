import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { WorkflowSteps } from './WorkflowSteps';
import { SuggestedActions } from './SuggestedActions';
import { ChatMessage } from './ChatMessage';
import { Send, Trash2 } from 'lucide-react';

export function AuditChat() {
  const { chatHistory, sendMessage, chatLoading, clearChat, sourceDocs } = useFinanceStudio();
  const [text, setText] = useState('');

  async function submit() {
    const t = text.trim();
    if (!t) return;
    setText('');
    await sendMessage(t);
  }

  return (
    <div className="audit-chat">
      <WorkflowSteps />
      <SuggestedActions />

      <div className="audit-chat__messages">
        {chatHistory.map(m => <ChatMessage key={m.id} msg={m} />)}
        {chatLoading && <div className="chat-msg chat-msg--loading">Thinking…</div>}
      </div>

      <div className="audit-chat__input">
        <div className="audit-chat__input-wrapper">
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); }
            }}
            placeholder="Start typing…"
            rows={1}
          />
          {sourceDocs.length > 0 && (
            <span className="audit-chat__source-count">{sourceDocs.length} sources</span>
          )}
          <button
            className="audit-chat__send-btn"
            onClick={submit}
            disabled={chatLoading || !text.trim()}
            aria-label="Send"
          >
            <Send size={16} />
          </button>
        </div>
        <button
          className="audit-chat__clear-btn"
          onClick={clearChat}
          disabled={chatLoading}
          aria-label="Clear chat"
          title="Clear chat"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}
