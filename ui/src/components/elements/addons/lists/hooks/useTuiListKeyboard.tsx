import { isArrowDown, isArrowUp, isEnter } from 'commons/components/utils/keyboard';
import { useCallback, useContext, useMemo } from 'react';
import Throttler from 'utils/Throttler';
import type { TuiListItemOnSelect } from '..';
import { TuiListItemsContext, type TuiListItemsState } from '../TuiListProvider';

const THROTTLER = new Throttler(10);

const useTuiListKeyboard = <T,>(onSelect: TuiListItemOnSelect<T>) => {
  const { items, movePrevious, moveNext } = useContext<TuiListItemsState<T>>(TuiListItemsContext);

  // Keyboard[keydown] event handler.
  const onKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // console.log(`kd[${event.key}]`);
      // event.preventDefault();

      // going up.
      if (isArrowUp(event.key)) {
        event.preventDefault();
        THROTTLER.debounce(() => movePrevious());
      }

      // going down.
      else if (isArrowDown(event.key)) {
        event.preventDefault();
        THROTTLER.debounce(() => moveNext());
      }

      // select.
      else if (isEnter(event.key)) {
        const index = items.findIndex(i => !!i.cursor);
        onSelect(items[index], index);
      }
    },
    [items, movePrevious, moveNext, onSelect]
  );

  // Register keyboard event handler.
  const register = useCallback(
    (element: HTMLElement) => {
      if (element) {
        element.addEventListener('keydown', onKeyDown);
      }
      return () => {
        element.removeEventListener('keydown', onKeyDown);
      };
    },
    [onKeyDown]
  );

  return useMemo(
    () => ({
      register
    }),
    [register]
  );
};

export default useTuiListKeyboard;
