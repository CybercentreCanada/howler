import type { ReactElement } from 'react';
import TuiList from './TuiList';
import TuiListElement from './TuiListElement';
import TuiListProvider from './TuiListProvider';

export type TuiListItemOnSelect<T> = (selection: TuiListItem<T>, rowIndex: number) => void;

export type TuiListItem<T> = {
  id: string | number;
  details?: boolean;
  cursor?: boolean;
  selected?: boolean;
  item: T;
};

export type TuiListItemProps<T> = {
  item: TuiListItem<T>;
  position: number;
};

export type TuiListMenuRenderer<T> = (props: TuiListItemProps<T>) => ReactElement | ReactElement[];

export type TuiListItemRenderer<T> = (props: TuiListItemProps<T>, classRenderer: () => string) => ReactElement;

export { TuiList, TuiListElement, TuiListProvider };
