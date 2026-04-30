import { useState } from 'react';
import { exportMessage } from '../lib/api';

interface ChatMessageActionsProps {
  messageId: string;
  content: string;
  hasTable?: boolean;
}

export function ChatMessageActions({ messageId, content, hasTable = false }: ChatMessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = content;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch (fallbackErr) {
        console.warn('Clipboard copy failed:', fallbackErr);
      }
    }
  };

  const handleExport = async (format: 'word' | 'pdf' | 'excel') => {
    const extensions = { word: 'docx', pdf: 'pdf', excel: 'xlsx' };
    setExporting(format);
    try {
      await exportMessage(messageId, format, `response.${extensions[format]}`);
    } catch (err) {
      console.error(`Export failed: ${err}`);
    } finally {
      setExporting(null);
    }
  };

  const btnStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '26px',
    height: '26px',
    borderRadius: '4px',
    border: 'none',
    background: 'transparent',
    color: 'var(--s-text-2, #888)',
    cursor: 'pointer',
    fontSize: '10px',
    fontWeight: 700,
    padding: 0,
    transition: 'all 0.15s ease',
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '2px',
      marginTop: '4px',
      opacity: 0.7,
      transition: 'opacity 0.15s ease',
    }}
    className="chat-msg-actions"
    onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
    onMouseLeave={e => (e.currentTarget.style.opacity = '0.7')}
    >
      <button title={copied ? 'Copied!' : 'Copy'} onClick={handleCopy} style={btnStyle}>
        {copied ? '✓' : '📋'}
      </button>
      <button
        title="Download Word"
        onClick={() => handleExport('word')}
        disabled={exporting === 'word'}
        style={{ ...btnStyle, opacity: exporting === 'word' ? 0.4 : 1 }}
      >
        {exporting === 'word' ? '⏳' : 'W'}
      </button>
      <button
        title="Download PDF"
        onClick={() => handleExport('pdf')}
        disabled={exporting === 'pdf'}
        style={{ ...btnStyle, opacity: exporting === 'pdf' ? 0.4 : 1 }}
      >
        {exporting === 'pdf' ? '⏳' : 'PDF'}
      </button>
      <button
        title={hasTable ? 'Download Excel' : 'No table in response'}
        onClick={() => hasTable && handleExport('excel')}
        disabled={!hasTable || exporting === 'excel'}
        style={{ ...btnStyle, opacity: (!hasTable || exporting === 'excel') ? 0.3 : 1 }}
      >
        {exporting === 'excel' ? '⏳' : 'XLS'}
      </button>
    </div>
  );
}
