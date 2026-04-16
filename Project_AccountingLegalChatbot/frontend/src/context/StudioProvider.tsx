import { createContext, useContext, useState, type ReactNode } from 'react';

export type Studio = 'legal' | 'financial' | 'regulatory' | 'settings';

interface StudioContextValue {
  activeStudio: Studio;
  setActiveStudio: (s: Studio) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

const StudioContext = createContext<StudioContextValue | null>(null);

export function StudioProvider({ children }: { children: ReactNode }) {
  const [activeStudio, setActiveStudio] = useState<Studio>('legal');
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <StudioContext.Provider value={{
      activeStudio,
      setActiveStudio,
      sidebarOpen,
      toggleSidebar: () => setSidebarOpen(o => !o),
    }}>
      {children}
    </StudioContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useStudio(): StudioContextValue {
  const ctx = useContext(StudioContext);
  if (!ctx) throw new Error('useStudio must be used inside <StudioProvider>');
  return ctx;
}
