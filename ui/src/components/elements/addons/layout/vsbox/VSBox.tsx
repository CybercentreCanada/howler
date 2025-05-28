import { Stack, type StackProps } from '@mui/material';
import { useAppBar, useAppBarHeight } from 'commons/components/app/hooks';
import { createContext, useLayoutEffect, useMemo, useRef, useState } from 'react';

type VSBoxProps = StackProps & {
  top?: number;
};

type VSBoxState = {
  header?: HTMLDivElement;
  content?: HTMLDivElement;
  top: number;
  scrollTop: number;
};

export const VSBoxContext = createContext<{ state: VSBoxState; setState?: (state: VSBoxState) => void }>({
  state: { top: 0, scrollTop: 0 }
});

const VSBox = ({ top, children, ...stackProps }: VSBoxProps) => {
  const ref = useRef<HTMLDivElement>();
  const appbarHeight = useAppBarHeight();
  const { autoHide } = useAppBar();
  const [state, setState] = useState<VSBoxState>({ top, scrollTop: top });

  useLayoutEffect(() => {
    // const tableHeader = content?.querySelector(':first-child[data-tuitable]') as HTMLDivElement;
    const header = ref.current?.querySelector('[data-vsbox-header]') as HTMLDivElement;
    const content = ref.current?.querySelector('[data-vsbox-content]') as HTMLDivElement;

    // Explicit top or appbar height.
    const _top = top !== undefined && top !== null ? top : autoHide ? 0 : appbarHeight;

    // We compute scroll top value on demand in order to ensure the
    //  header element is fully rendered.
    const _scrollTop = _top + (header?.offsetHeight || 0);

    setState({ top: _top, scrollTop: _scrollTop, header, content });
  }, [top, appbarHeight, autoHide]);

  const _value = useMemo(() => ({ state, setState }), [state]);

  return (
    <VSBoxContext.Provider value={_value}>
      <Stack id="vs-box" ref={ref} height="fit-content" {...stackProps}>
        {children}
      </Stack>
    </VSBoxContext.Provider>
  );
};

export default VSBox;
