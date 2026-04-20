import type { ReactNode } from 'react';

interface Props {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

export function ThreePaneLayout({ left, center, right }: Props) {
  return (
    <div className="three-pane-layout">
      {left}
      <div className="three-pane-layout__center" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 0', overflowY: 'auto', minHeight: 0 }}>
        {center}
      </div>
      {right}
    </div>
  );
}
