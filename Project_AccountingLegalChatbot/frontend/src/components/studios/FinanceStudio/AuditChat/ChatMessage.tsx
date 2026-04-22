import type { ChatMessage as CM } from '../types';
import { FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { normalizeMarkdown } from '../../LegalStudio/ChatMessages';

export function ChatMessage({ msg }: { msg: CM }) {
  return (
    <div className={`chat-msg chat-msg--${msg.role}`} data-testid={`msg-${msg.id}`}>
      <div className="chat-msg__content">
        {msg.role === 'assistant' ? (
          <div className="report-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{normalizeMarkdown(msg.content)}</ReactMarkdown>
          </div>
        ) : (
          msg.content
        )}
      </div>
      {msg.citations?.length > 0 && (
        <div className="chat-msg__citations">
          {msg.citations.map((c, i) => (
            <span key={i} className="citation-chip">
              <FileText size={10} />
              {c.doc_id}{c.page ? ` p.${c.page}` : ''}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
