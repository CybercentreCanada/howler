import type { FC, PropsWithChildren, ReactNode } from 'react';
import { createContext, useCallback, useState } from 'react';

interface AppBarItem {
  id: string;
  component: ReactNode;
}

export interface AppBarContextType {
  leftItems: AppBarItem[];
  rightItems: AppBarItem[];
  addToAppBar: (alignment: 'left' | 'right', id: string, component: ReactNode) => void;
  removeFromAppBar: (id: string) => void;
}

export const AppBarContext = createContext<AppBarContextType>(null);

const AppBarProvider: FC<PropsWithChildren> = ({ children }) => {
  const [leftItems, setLeftItems] = useState<AppBarItem[]>([]);
  const [rightItems, setRightItems] = useState<AppBarItem[]>([]);

  const addToAppBar = useCallback((alignment: 'left' | 'right', id: string, component: ReactNode) => {
    const setter = alignment === 'left' ? setLeftItems : setRightItems;
    setter(prev => {
      if (prev.some(item => item.id === id)) {
        return prev;
      }
      return [...prev, { id, component }];
    });
  }, []);

  const removeFromAppBar = useCallback((id: string) => {
    setLeftItems(prev => prev.filter(item => item.id !== id));
    setRightItems(prev => prev.filter(item => item.id !== id));
  }, []);

  return (
    <AppBarContext.Provider value={{ leftItems, rightItems, addToAppBar, removeFromAppBar }}>
      {children}
    </AppBarContext.Provider>
  );
};

export default AppBarProvider;
