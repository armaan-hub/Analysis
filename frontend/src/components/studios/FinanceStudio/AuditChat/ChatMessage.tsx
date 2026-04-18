import type { ChatMessage as CM } from '../types';

export function ChatMessage({ msg }: { msg: CM }) {
  return (
    <div className={`chat-msg chat-msg--${msg.role}`} data-testid={`msg-${msg.id}`}>
      <div className="chat-msg__content">{msg.content}</div>
      {msg.citations?.length > 0 && (
        <div className="chat-msg__citations">
          {msg.citations.map((c, i) => (
            <span key={i} className="citation-chip">
              {c.doc_id}{c.page ? ` p.${c.page}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
