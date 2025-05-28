import { Collapse } from '@mui/material';
import AppListEmpty from 'commons/components/display/AppListEmpty';
import { get } from 'lodash-es';
import { useCallback } from 'react';
import type { TuiTableCellRenderer, TuiTableColumn, TuiTableRowDetailRenderer } from '.';
import type { TuiListItemOnSelect, TuiListItemProps, TuiListMenuRenderer } from '..';
import { TuiListElement } from '..';
import TuiListBase from '../TuiListBase';
import type TuiTableLayout from './TuiTableLayout';

type TuiTableBodyProps<T> = {
  keyboard?: boolean;
  layout: TuiTableLayout;
  columns: TuiTableColumn[];
  onRowSelect?: TuiListItemOnSelect<T>;
  menuRenderer?: TuiListMenuRenderer<T>;
  detailRenderer?: TuiTableRowDetailRenderer<T>;
  children?: TuiTableCellRenderer<T>;
};

const TuiTableBody = <T,>({
  keyboard,
  layout,
  columns,
  onRowSelect,
  menuRenderer,
  detailRenderer,
  children
}: TuiTableBodyProps<T>) => {
  const trowRenderer = useCallback(
    (props: TuiListItemProps<T>, classRenderer) => {
      return (
        <div className={`tui-table-row ${classRenderer()}`}>
          <div style={{ display: 'flex', position: 'relative' }}>
            {columns.map((column, columnIndex) => {
              const value = get(props.item.item, column.path || column.column, '');
              return (
                <div
                  key={column.column}
                  className="tui-table-cell"
                  style={{ minWidth: layout.getWidth(column.column) }}
                >
                  {children ? children(value, columnIndex, column, props) : <div>{value as any}</div>}
                </div>
              );
            })}
            {menuRenderer && menuRenderer(props)}
          </div>
          {detailRenderer && (
            <Collapse in={props.item.details} unmountOnExit>
              {detailRenderer(props)}
            </Collapse>
          )}
        </div>
      );
    },
    [layout, columns, menuRenderer, detailRenderer, children]
  );

  return (
    <TuiListBase keyboard={keyboard} onSelect={onRowSelect}>
      {(items, onClick) => {
        return items.length > 0 ? (
          items.map((item, index) => (
            <TuiListElement key={item.id} item={item} position={index} onSelect={onClick}>
              {trowRenderer}
            </TuiListElement>
          ))
        ) : (
          <AppListEmpty mt={4} />
        );
      }}
    </TuiListBase>
  );
};

export default TuiTableBody;
