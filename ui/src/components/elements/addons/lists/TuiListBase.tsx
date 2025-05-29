import { emphasize, styled } from '@mui/material';
import { useAppBar, useAppBarHeight, useAppLayout } from 'commons/components/app/hooks';
import useTuiListKeyboard from 'components/elements/addons/lists/hooks/useTuiListKeyboard';
import { memo, useCallback, useContext, useEffect, useLayoutEffect, useRef, type ReactNode } from 'react';
import type { TuiListItem, TuiListItemOnSelect } from '.';
import {
  TuiListItemsContext,
  TuiListMethodContext,
  type TuiListItemsState,
  type TuiListMethodsState
} from './TuiListProvider';

const TuiListBaseRoot = styled('div')(({ theme }) => ({
  outline: 'none',
  backgroundColor: theme.palette.background.default,

  '.elementFocus': {
    backgroundColor: emphasize(theme.palette.background.default, 0.02),
    '& .actions': {
      display: 'flex',
      backgroundColor: emphasize(theme.palette.background.default, 0.02)
    }
  },

  '.elementHover': {
    '&:hover': {
      cursor: 'pointer',
      backgroundColor: emphasize(theme.palette.background.default, 0.03)
    },
    '&:hover .actions': {
      display: 'flex',
      backgroundColor: emphasize(theme.palette.background.default, 0.03)
    }
  },

  '.elementSelected': {
    backgroundColor: emphasize(theme.palette.background.default, 0.04),
    '& .actions': {
      display: 'flex',
      backgroundColor: emphasize(theme.palette.background.default, 0.04)
    }
  }
}));

export type TuiListItemsRenderer<T> = (items: TuiListItem<T>[], onSelect: TuiListItemOnSelect<T>) => ReactNode;

type TuiListBaseProps<T> = {
  keyboard?: boolean;
  onSelect: TuiListItemOnSelect<T>;
  children: TuiListItemsRenderer<T>;
};

const TuiListBase = <T,>({ keyboard = false, onSelect, children }: TuiListBaseProps<T>) => {
  const listEl = useRef<HTMLDivElement>();
  const appbar = useAppBar();
  const appbarHeight = useAppBarHeight();
  const layout = useAppLayout();
  const { items } = useContext<TuiListItemsState<T>>(TuiListItemsContext);
  const { select } = useContext<TuiListMethodsState<T>>(TuiListMethodContext);

  const onItemSelect = useCallback(
    (selection: TuiListItem<T>, index: number) => {
      const newItem = select(selection, index);
      if (onSelect) {
        onSelect(newItem, index);
      }
    },
    [select, onSelect]
  );

  const { register } = useTuiListKeyboard(onItemSelect);

  useEffect(() => {
    if (keyboard) {
      return register(listEl.current);
    }
  }, [keyboard, register]);

  useLayoutEffect(() => {
    if (keyboard) {
      listEl.current.focus({ preventScroll: true });
    }
  }, [keyboard]);

  return (
    <TuiListBaseRoot
      ref={listEl}
      tabIndex={-1}
      data-tuiappbar-height={appbarHeight}
      data-tuilayout={layout.current}
      data-tuiappbar-autohide={appbar.autoHide}
    >
      {children(items, onItemSelect)}
    </TuiListBaseRoot>
  );
};

export default memo(TuiListBase);
