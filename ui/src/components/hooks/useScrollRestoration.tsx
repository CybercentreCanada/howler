/**
 * Currently, the react-router scrollrestoration component only works at the window level.
 * This implementation handle it at the element level, use it in the route that requires it.
 * Inspired from https://github.com/remix-run/react-router/pull/10468
 * Possible this won't work on a remix project.
 */

import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';

const getScrollPosition = (key: string) => {
  const pos = window.sessionStorage.getItem(key);
  return Number(pos) || 0;
};

const setScrollPosition = (key: string, pos: number) => {
  try {
    window.sessionStorage.setItem(key, pos.toString());
  } catch {
    // eslint-disable-next-line no-console
    console.log('Session storage full, can not save the scroll position');
  }
};

// this currently can only handle one main container
export const useScrollRestoration = (element: string = 'app-scrollct') => {
  const key = `scroll-position-${useLocation().key}`;

  //set scroll position on mount, save scroll position on unmount
  useLayoutEffect(() => {
    document.getElementById(element).scrollTo(0, getScrollPosition(key));

    return () => {
      setScrollPosition(key, document.getElementById(element).scrollTop ?? 0);
    };
  }, [element, key]);
};
