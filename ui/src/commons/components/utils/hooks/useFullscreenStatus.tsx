import { useCallback, useLayoutEffect, useMemo, useState, type MutableRefObject } from 'react';

const getBrowserFullscreenElementProp = () => {
  if (typeof document.fullscreenElement !== 'undefined') {
    return 'fullscreenElement';
  }
  // eslint-disable-next-line @typescript-eslint/dot-notation
  if (typeof document['mozFullScreenElement'] !== 'undefined') {
    return 'mozFullScreenElement';
  }
  // eslint-disable-next-line @typescript-eslint/dot-notation
  if (typeof document['msFullscreenElement'] !== 'undefined') {
    return 'msFullscreenElement';
  }
  // eslint-disable-next-line @typescript-eslint/dot-notation
  if (typeof document['webkitFullscreenElement'] !== 'undefined') {
    return 'webkitFullscreenElement';
  }
  throw new Error('fullscreenElement is not supported by this browser');
};

export default function useFullscreenStatus(elRef: MutableRefObject<any>) {
  const [isFullscreen, setIsFullscreen] = useState(document[getBrowserFullscreenElementProp()] != null);

  const setFullscreen = useCallback(() => {
    if (elRef.current == null) return;

    elRef.current
      .requestFullscreen()
      .then(() => {
        setIsFullscreen(document[getBrowserFullscreenElementProp()] != null);
      })
      .catch(() => {
        setIsFullscreen(false);
      });
  }, [elRef]);

  useLayoutEffect(() => {
    document.onfullscreenchange = () => setIsFullscreen(document[getBrowserFullscreenElementProp()] != null);

    return () => {
      document.onfullscreenchange = undefined;
    };
  });

  return useMemo(() => [isFullscreen, setFullscreen], [isFullscreen, setFullscreen]) as [boolean, () => void];
}
