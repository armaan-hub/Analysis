import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import { ModePills, MODE_PLACEHOLDERS, type ChatMode } from './ModePills';
import { AttachButton } from './AttachButton';
import { AttachedFileChips, type AttachedFile } from './AttachedFileChips';

interface Props {
  onSend: (text: string, attachedFiles?: File[]) => void;
  disabled?: boolean;
  initialValue?: string;
  mode?: ChatMode;
  onModeChange?: (m: ChatMode) => void;
}

export function ChatInput({ onSend, disabled, initialValue = '', mode = 'fast', onModeChange }: Props) {
  const [value, setValue] = useState(initialValue);
  const [attachedFiles, setAttachedFiles] = useState<Array<AttachedFile & { file: File }>>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const idCounter = useRef(0);

  useEffect(() => {
    const handler = (e: Event) => {
      const text = (e as CustomEvent<string>).detail;
      setValue(text);
      textareaRef.current?.focus();
    };
    window.addEventListener('studio:suggest', handler);
    return () => window.removeEventListener('studio:suggest', handler);
  }, []);

  const autoResize = useCallback(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, []);

  const submit = useCallback(() => {
    const text = value.trim();
    if (!text || disabled) return;
    const files = attachedFiles.map(f => f.file);
    onSend(text, files.length > 0 ? files : undefined);
    setValue('');
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }, [value, disabled, attachedFiles, onSend]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleAttach = useCallback((fileList: FileList) => {
    const newFiles = Array.from(fileList).map(file => ({
      id: `attach-${++idCounter.current}`,
      name: file.name,
      file,
    }));
    setAttachedFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleRemoveAttach = useCallback((id: string) => {
    setAttachedFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  const hasContent = value.trim().length > 0;

  return (
    <div className="chat-input-area">
      <div className="chat-input-container">
        <div className="chat-input-row">
          <AttachButton onAttach={handleAttach} disabled={disabled} />
          <textarea
            ref={textareaRef}
            className="chat-input-textarea"
            value={value}
            onChange={e => { setValue(e.target.value); autoResize(); }}
            onKeyDown={handleKeyDown}
            placeholder={MODE_PLACEHOLDERS[mode]}
            disabled={disabled}
            rows={1}
          />
          <button
            type="button"
            className={`chat-send-btn ${hasContent ? 'chat-send-btn--active' : 'chat-send-btn--inactive'}`}
            onClick={submit}
            disabled={disabled || !hasContent}
            aria-label="Send message"
            title="Send"
          >
            <Send size={16} />
          </button>
        </div>
        <AttachedFileChips files={attachedFiles} onRemove={handleRemoveAttach} />
        {onModeChange && (
          <ModePills value={mode} onChange={onModeChange} />
        )}
        {mode === 'deep_research' && (
          <div className="deep-research-info">
            <div className="deep-research-info__label">🔬 Deep Research Mode</div>
            <div className="deep-research-info__desc">
              AI will search across all sources, cross-reference citations, and produce a comprehensive research report.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export type { ChatMode };
