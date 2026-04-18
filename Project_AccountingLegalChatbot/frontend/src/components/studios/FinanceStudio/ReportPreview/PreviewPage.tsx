export function PreviewPage({ pageNumber, children }: { pageNumber: number; children: React.ReactNode }) {
  return (
    <div className="preview-page">
      <div className="preview-page__body">{children}</div>
      <div className="preview-page__footer">Page {pageNumber}</div>
    </div>
  );
}
