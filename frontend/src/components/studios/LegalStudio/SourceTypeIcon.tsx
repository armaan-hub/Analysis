function getTypeFromFilename(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  if (ext === 'pdf') return 'pdf';
  if (ext === 'doc' || ext === 'docx') return 'doc';
  if (ext === 'txt') return 'txt';
  if (ext === 'csv') return 'csv';
  if (ext === 'xls' || ext === 'xlsx') return 'xls';
  if (filename.startsWith('http') || ext === 'url') return 'url';
  return 'txt';
}

const LABELS: Record<string, string> = {
  pdf: 'PDF',
  doc: 'DOC',
  txt: 'TXT',
  url: 'URL',
  csv: 'CSV',
  xls: 'XLS',
};

interface Props {
  filename: string;
}

export function SourceTypeIcon({ filename }: Props) {
  const type = getTypeFromFilename(filename);
  return (
    <div className={`source-type-icon source-type-icon--${type}`}>
      {LABELS[type] ?? 'TXT'}
    </div>
  );
}
