import { Search } from 'lucide-react';

interface Props {
  value: string;
  onChange: (value: string) => void;
}

export function SourceSearch({ value, onChange }: Props) {
  return (
    <div className="source-search">
      <div className="source-search__wrapper">
        <Search size={14} className="source-search__icon" />
        <input
          className="source-search__input"
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="Search sources…"
          aria-label="Search sources"
        />
      </div>
    </div>
  );
}
