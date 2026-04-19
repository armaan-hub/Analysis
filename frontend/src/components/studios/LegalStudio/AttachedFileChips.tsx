interface AttachedFile {
  id: string;
  name: string;
}

interface Props {
  files: AttachedFile[];
  onRemove: (id: string) => void;
}

export function AttachedFileChips({ files, onRemove }: Props) {
  if (files.length === 0) return null;

  return (
    <div className="attached-chips">
      {files.map(f => (
        <div key={f.id} className="file-chip">
          <span>📄</span>
          <span>{f.name}</span>
          <button
            type="button"
            className="file-chip__remove"
            onClick={() => onRemove(f.id)}
            aria-label={`Remove ${f.name}`}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export type { AttachedFile };
