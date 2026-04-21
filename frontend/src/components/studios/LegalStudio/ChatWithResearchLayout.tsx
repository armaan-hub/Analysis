import type { ReactNode } from 'react';

interface Props {
  modePills: ReactNode;
  chatArea: ReactNode;
  researchPanel: ReactNode;
}

export function ChatWithResearchLayout({ modePills, chatArea, researchPanel }: Props) {
  return (
    <div className="chat-research-layout">
      <div className="chat-research-layout__main">
        <div className="chat-research-layout__pills">{modePills}</div>
        <div className="chat-research-layout__chat">{chatArea}</div>
      </div>
      <div className="chat-research-layout__side">{researchPanel}</div>
    </div>
  );
}
