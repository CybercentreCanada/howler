import { useLayoutEffect, useState } from 'react';

export const APPBAR_READY_EVENT = 'tui.event.appbar.ready';

export function useAppBarHeight(): number {
  const [height, setHeight] = useState<number>(-1);

  const updateHeight = () => {
    const appbar = document.getElementById('appbar');
    if (appbar) {
      const rect = appbar.getBoundingClientRect();
      setHeight(rect.height);
    }
  };

  useLayoutEffect(() => {
    updateHeight();
    window.addEventListener('resize', updateHeight);
    window.addEventListener(APPBAR_READY_EVENT, updateHeight);
    return () => {
      window.removeEventListener('resize', updateHeight);
      window.removeEventListener(APPBAR_READY_EVENT, updateHeight);
    };
  }, []);

  return height;
}
