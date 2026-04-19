import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import { ModeDropdown, type ChatMode } from './ModeDropdown';

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
  initialValue?: string;
  mode?: ChatMode;
  onModeChange?: (m: ChatMode) => void;
}

export function ChatInput({ onSend, disabled, initialValue = '', mode = 'normal', onModeChange }: Props) {
  const [value, setValue] = useState(initialValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Pick up suggestion clicks from empty state
  useEffect(() => {
    const handler = (e: Event) => {
      const text = (e as CustomEvent<string>).detail;
      setValue(text);
      textareaRef.current?.focus();
    };
    window.addEventListener('studio:suggest', handler);
    return () => window.removeEventListener('studio:suggest', handler);
  }, []);

  const autoResize = () => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  };

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="chat-input-bar">
      {onModeChange && (
        <ModeDropdown value={mode} onChange={onModeChange} />
      )}
      <textarea
        ref={textareaRef}
        className="chat-input-field"
        value={value}
        onChange={e => { setValue(e.target.value); autoResize(); }}
        onKeyDown={handleKeyDown}
        placeholder="Ask about regulations, tax law, compliance…  (Shift+Enter for new line)"
        disabled={disabled}
        rows={1}
      />
      <button
        type="button"
        className="chat-input-send"
        onClick={submit}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        title="Send"
      >
        <Send size={16} />
      </button>
    </div>
  );
}
