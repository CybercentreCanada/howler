import { useCallback, useLayoutEffect, useMemo, useState, type MutableRefObject } from 'react';

type FullscreenDocument = Document & {
  mozFullScreenElement?: Element | null;
  msFullscreenElement?: Element | null;
  webkitFullscreenElement?: Element | null;
};

const getBrowserFullscreenElementProp = (): keyof FullscreenDocument => {
  const fullscreenDocument = document as FullscreenDocument;

  if (typeof fullscreenDocument.fullscreenElement !== 'undefined') {
    return 'fullscreenElement';
  }
  if (typeof fullscreenDocument.mozFullScreenElement !== 'undefined') {
    return 'mozFullScreenElement';
  }
  if (typeof fullscreenDocument.msFullscreenElement !== 'undefined') {
    return 'msFullscreenElement';
  }
  if (typeof fullscreenDocument.webkitFullscreenElement !== 'undefined') {
    return 'webkitFullscreenElement';
  }
  throw new Error('fullscreenElement is not supported by this browser');
};

export default function useFullscreenStatus(elRef: MutableRefObject<any>) {
  const fullscreenDocument = document as FullscreenDocument;
  const [isFullscreen, setIsFullscreen] = useState(fullscreenDocument[getBrowserFullscreenElementProp()] != null);

  const setFullscreen = useCallback(() => {
    if (elRef.current == null) {
      return;
    }

    elRef.current
      .requestFullscreen()
      .then(() => {
        setIsFullscreen(fullscreenDocument[getBrowserFullscreenElementProp()] != null);
      })
      .catch(() => {
        setIsFullscreen(false);
      });
  }, [elRef]);

  useLayoutEffect(() => {
    document.onfullscreenchange = () => setIsFullscreen(fullscreenDocument[getBrowserFullscreenElementProp()] != null);

    return () => {
      document.onfullscreenchange = null;
    };
  }, []);

  return useMemo(() => [isFullscreen, setFullscreen], [isFullscreen, setFullscreen]) as [boolean, () => void];
}
