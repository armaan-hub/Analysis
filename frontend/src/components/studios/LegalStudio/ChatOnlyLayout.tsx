import type { ReactNode } from 'react';

interface Props {
  modePills: ReactNode;
  chatArea: ReactNode;
}

export function ChatOnlyLayout({ modePills, chatArea }: Props) {
  return (
    <div className="chat-only-layout">
      <div className="chat-only-layout__pills">{modePills}</div>
      <div className="chat-only-layout__chat">{chatArea}</div>
    </div>
  );
}
