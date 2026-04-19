import { useState, useRef, type DragEvent } from 'react';

interface Props {
  onUpload: (files: FileList) => void;
  onClose: () => void;
}

export function AddSourcesOverlay({ onUpload, onClose }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      onUpload(e.dataTransfer.files);
      onClose();
    }
  };

  const handleBrowse = () => {
    fileRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onUpload(e.target.files);
      onClose();
    }
  };

  return (
    <div className="add-sources-overlay">
      <input
        ref={fileRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <div
        className={`add-sources-dropzone${dragOver ? ' add-sources-dropzone--dragover' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        <div className="add-sources-dropzone__icon">📁</div>
        <div className="add-sources-dropzone__title">Drop files here or browse</div>
        <div className="add-sources-dropzone__desc">Select multiple files at once</div>
        <button
          type="button"
          className="add-sources-browse-btn"
          onClick={handleBrowse}
        >
          Browse Files
        </button>
        <div className="add-sources-formats">PDF · DOCX · TXT · CSV · XLSX</div>
      </div>
      <button
        type="button"
        className="add-sources-url-btn"
        onClick={() => { /* URL paste modal - future */ }}
      >
        🔗 Paste a URL
      </button>
    </div>
  );
}
