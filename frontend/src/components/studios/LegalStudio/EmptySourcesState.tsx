interface Props {
  onAddSources: () => void;
}

export function EmptySourcesState({ onAddSources }: Props) {
  return (
    <div className="empty-sources">
      <div className="empty-sources__icon">📚</div>
      <div className="empty-sources__title">No sources yet</div>
      <div className="empty-sources__desc">
        Add documents, URLs, or files<br />to start your analysis
      </div>
      <button
        type="button"
        className="empty-sources__btn"
        onClick={onAddSources}
      >
        + Add Sources
      </button>
    </div>
  );
}
