import type { ReactNode } from 'react';
import { createContext, useCallback, useMemo, useState } from 'react';
import type { TuiListItem } from '.';

export type TuiListMethodsState<T> = {
  load: (items: TuiListItem<T>[]) => void;
  move: (index: number) => void;
  select: (item: TuiListItem<T>, index: number) => TuiListItem<T>;
  replace: (item: TuiListItem<T>, newItem: TuiListItem<T>) => void;
  replaceById: (item: TuiListItem<T>, newItem: TuiListItem<T>) => void;
  remove: (id: string) => void;
};

export type TuiListItemsState<T> = {
  items: TuiListItem<T>[];
  moveNext: () => void;
  movePrevious: () => void;
};

const DEFAULT_METHODS_STATE = {
  load: () => null,
  move: () => null,
  select: () => null,
  replace: () => null,
  replaceById: () => null,
  remove: () => null
};

const DEFAULT_ITEMS_STATE = {
  size: 0,
  items: [],
  movePrevious: () => null,
  moveNext: () => null
};

export const TuiListMethodContext = createContext<TuiListMethodsState<any>>(DEFAULT_METHODS_STATE);

export const TuiListItemsContext = createContext<TuiListItemsState<any>>(DEFAULT_ITEMS_STATE);

type TuiListProviderProps = {
  children: ReactNode;
};

const TuiListProvider = <T,>({ children }: TuiListProviderProps) => {
  const [items, setItems] = useState<TuiListItem<T>[]>([]);

  const load = useCallback((_items: TuiListItem<T>[]) => {
    setItems(current => {
      return _items.map(i => {
        const previous = current.find(_i => i.id === _i.id);
        if (previous) {
          return {
            ...i,
            cursor: i.cursor === undefined ? previous.cursor : i.cursor,
            selected: i.selected === undefined ? previous.selected : i.selected,
            details: i.details === undefined ? previous.details : i.details
          };
        }
        return i;
      });
    });
  }, []);

  const select = useCallback((item: TuiListItem<T>, index: number) => {
    const newItem = { ...item, cursor: true, selected: item ? !item.selected : true };
    setItems(current => {
      return current.map((_item, _index) => {
        if (index === _index) {
          return newItem;
        } else if (_item.selected || _item.cursor) {
          return { ..._item, cursor: false, selected: false };
        }
        return _item;
      });
    });
    return newItem;
  }, []);

  const move = useCallback((index: number) => {
    setItems(current => {
      return current.map((_item, _index) => {
        if (index === _index) {
          return { ..._item, cursor: true };
        } else if (_item.cursor) {
          return { ..._item, cursor: false };
        }
        return _item;
      });
    });
  }, []);

  const replace = useCallback((item: TuiListItem<T>, newItem: TuiListItem<T>) => {
    setItems(current => {
      const index = current.findIndex(i => i === item);
      if (index > -1) {
        current[index] = { ...current[index], ...newItem };
      }
      return [...current];
    });
  }, []);

  const replaceById = useCallback((item: TuiListItem<T>, newItem: TuiListItem<T>) => {
    setItems(current => {
      const index = current.findIndex(i => i.id === item.id);
      if (index > -1) {
        current[index] = { ...current[index], ...newItem };
      }
      return [...current];
    });
  }, []);

  const remove = useCallback((id: string) => {
    setItems(current => {
      const index = current.findIndex(i => i.id === id);
      if (index > -1) {
        return current.filter(i => i.id !== id);
      }
      return [...current];
    });
  }, []);

  const moveNext = useCallback(() => {
    const cursor = items.findIndex(i => !!i.cursor);
    const next = cursor + 1 > items.length - 1 ? 0 : cursor + 1;
    move(next);
  }, [items, move]);

  const movePrevious = useCallback(() => {
    const cursor = items.findIndex(i => !!i.cursor);
    const next = cursor - 1 < 0 ? items.length - 1 : cursor - 1;
    move(next);
  }, [items, move]);

  const _items = useMemo(
    () => ({
      items,
      moveNext,
      movePrevious
    }),
    [items, moveNext, movePrevious]
  );

  const _functions = useMemo(
    () => ({
      load,
      move,
      select,
      replace,
      replaceById,
      remove
    }),
    [load, select, move, replace, replaceById, remove]
  );

  return (
    <TuiListMethodContext.Provider value={_functions}>
      <TuiListItemsContext.Provider value={_items}>{children}</TuiListItemsContext.Provider>
    </TuiListMethodContext.Provider>
  );
};

export default TuiListProvider;
