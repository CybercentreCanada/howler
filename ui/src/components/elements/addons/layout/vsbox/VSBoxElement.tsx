import type { BoxProps } from '@mui/material';
import type { ReactElement } from 'react';
import { memo, useContext, useLayoutEffect, useRef } from 'react';
import { VSBoxContext } from './VSBox';

type VSBoxElementProps = Omit<BoxProps, 'children'> & {
  focus: boolean;
  children: ReactElement;
};
const VSBoxElement = ({ focus, children }: VSBoxElementProps) => {
  const {
    state: { header, content, scrollTop }
  } = useContext(VSBoxContext);
  const ref = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    const element = ref.current;

    if (focus && element && element.offsetParent) {
      // if the first child of the vsbox content is a table,
      //  then we'll offset the scroll bar by the height of
      //  it header.
      const tableHeader = content?.querySelector(
        ':first-child[data-tuitable] [data-tuitable-header]'
      ) as HTMLDivElement;

      // the amount of offset to add to scroll bar.
      // this accounts for the vsbox header and a tuitable header.
      const hh = scrollTop + (tableHeader?.offsetHeight || 0);

      // offsetParent has no offsetHeight, so we use bounding client object.
      const parent = element.offsetParent.getBoundingClientRect();

      // visual frame of reference.
      const fStart = element.offsetParent.scrollTop + hh;
      const fEnd = fStart + parent.height - hh;

      // element frame of reference.
      const eStart = element.offsetTop;
      const eEnd = eStart + element.offsetHeight;

      // Determine scroll direction
      if (eStart < fStart) {
        element.offsetParent.scrollBy({ top: eStart - fStart });
      } else if (eEnd > fEnd) {
        element.offsetParent.scrollBy({ top: eEnd - fEnd });
      } else {
        // element is within visual frame.
      }
    }
  }, [header, content, scrollTop, focus]);

  return (
    <div ref={ref} className="tui-vsbox-element">
      {children}
    </div>
  );
};

export default memo(VSBoxElement);
