import type { ReactNode } from 'react';
import type { TuiListItemProps } from '..';

export const MATCHERS = ['like', 'in', 'is', '>=', '<=', '='] as const;
export type TuiSearchMatcher = (typeof MATCHERS)[number];

export type TuiTableColumn = {
  column: string;
  label?: string;
  i18nKey?: string;
  operators?: TuiSearchMatcher[];
  path?: string;
  sortable?: boolean;
  width?: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12;
};

export type TuiTableRowDetailRenderer<T> = (props: TuiListItemProps<T>) => ReactNode;

export type TuiTableCellRenderer<T> = (
  value: any,
  columnIndex: number,
  column: TuiTableColumn,
  props: TuiListItemProps<T>
) => ReactNode;
