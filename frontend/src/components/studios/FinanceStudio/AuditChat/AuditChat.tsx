import { useState } from 'react';
import { useFinanceStudio } from '../FinanceStudioContext';
import { WorkflowSteps } from './WorkflowSteps';
import { SuggestedActions } from './SuggestedActions';
import { ChatMessage } from './ChatMessage';

export function AuditChat() {
  const { chatHistory, sendMessage, chatLoading, clearChat } = useFinanceStudio();
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
        {chatLoading && <div className="chat-msg chat-msg--loading">…</div>}
      </div>

      <div className="audit-chat__input">
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); }
          }}
          placeholder="Ask about the audit…"
          rows={2}
        />
        <button onClick={submit} disabled={chatLoading || !text.trim()}>Send</button>
        <button onClick={clearChat} disabled={chatLoading}>Clear</button>
      </div>
    </div>
  );
}
