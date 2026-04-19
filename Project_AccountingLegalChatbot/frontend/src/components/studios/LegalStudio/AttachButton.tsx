import { useRef } from 'react';
import { Plus } from 'lucide-react';

interface Props {
  onAttach: (files: FileList) => void;
  disabled?: boolean;
}

export function AttachButton({ onAttach, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={e => {
          if (e.target.files && e.target.files.length > 0) {
            onAttach(e.target.files);
            e.target.value = '';
          }
        }}
      />
      <button
        type="button"
        className="attach-btn"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        aria-label="Attach files"
        title="Attach files"
      >
        <Plus size={18} />
      </button>
    </>
  );
}
