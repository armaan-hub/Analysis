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
      <div className="three-pane-layout__center">
        {center}
      </div>
      {right}
    </div>
  );
}
