import { darken, emphasize, lighten, styled } from '@mui/material';
import FlexPort from 'components/elements/addons/layout/FlexPort';
import { useEffect, useRef, useState } from 'react';
import { useResizeDetector } from 'react-resize-detector';
import type { TuiTableCellRenderer, TuiTableColumn, TuiTableRowDetailRenderer } from '.';
import type { TuiListItemOnSelect, TuiListMenuRenderer } from '..';
import TuiTableBody from './TuiTableBody';
import TuiTableHead from './TuiTableHead';
import TuiTableLayout from './TuiTableLayout';

const TableRoot = styled('div')(({ theme }) => ({
  flex: 1,

  display: 'flex',

  flexDirection: 'column',

  '.tui-table-row': {
    wordBreak: 'break-all',
    borderBottom: '1px solid',
    borderBottomColor:
      theme.palette.mode === 'dark'
        ? lighten(theme.palette.background.default, 0.05)
        : darken(theme.palette.background.default, 0.05)
  },

  '.tui-table-cell': {
    padding: theme.spacing(1)
  },

  '.tui-table-header': {
    display: 'flex',
    alignItems: 'center',
    border: '1px dotted transparent',
    padding: theme.spacing(1)
  },

  '.tui-table-header-active': {
    border: '1px dotted',
    borderColor: emphasize(theme.palette.background.default, 0.25),
    backgroundColor: emphasize(theme.palette.background.default, 0.05)
  },

  '.tui-table-header-hover': {
    '&:hover': {
      cursor: 'pointer',
      backgroundColor: emphasize(theme.palette.background.default, 0.05)
    },
    '&:hover .tui-table-header-menu-btn': {
      opacity: 1
    }
  },

  '.tui-table-header-menu': {},

  '.tui-table-header-menu-btn': {
    opacity: 0
  },

  '.tui-table-head': {
    display: 'flex',
    backgroundColor: theme.palette.background.default,
    zIndex: theme.zIndex.appBar - 2
  },

  '.tui-table-divider': {
    borderBottom: '1px solid',
    borderBottomColor: theme.palette.divider
  }
}));

type TuiTableProps<T> = {
  keyboard?: boolean;
  flexPort?: boolean;
  headless?: boolean;
  columns: TuiTableColumn[];
  onRowSelect?: TuiListItemOnSelect<T>;
  menuRenderer?: TuiListMenuRenderer<T>;
  detailRenderer?: TuiTableRowDetailRenderer<T>;
  children?: TuiTableCellRenderer<T>;
};

const TuiTable = <T,>({
  keyboard,
  flexPort,
  headless,
  columns,
  onRowSelect,
  menuRenderer,
  detailRenderer,
  children
}: TuiTableProps<T>) => {
  const { width, ref } = useResizeDetector({ handleHeight: false });
  const { width: bodyWidth, ref: bodyRef } = useResizeDetector({ handleHeight: false });
  const [layout, setLayout] = useState<TuiTableLayout>();
  const widthRef = useRef<number>(width);

  useEffect(() => {
    if (!flexPort || !layout) {
      if (width && width !== widthRef.current) {
        setLayout(new TuiTableLayout(width, width, columns));
      }
      widthRef.current = width;
    }
  }, [flexPort, layout, width, columns]);

  useEffect(() => {
    if (flexPort && layout) {
      if (bodyWidth && bodyWidth !== widthRef.current) {
        setLayout(new TuiTableLayout(width, bodyWidth, columns));
      }
      widthRef.current = bodyWidth;
    }
  }, [flexPort, layout, width, bodyWidth, columns]);

  return (
    <TableRoot ref={ref} data-tuitable="true">
      {!headless && layout && <TuiTableHead layout={layout} columns={columns} />}
      {layout &&
        (flexPort ? (
          <FlexPort>
            <div ref={bodyRef}>
              <TuiTableBody
                keyboard={keyboard}
                layout={layout}
                columns={columns}
                onRowSelect={onRowSelect}
                menuRenderer={menuRenderer}
                detailRenderer={detailRenderer}
              >
                {children}
              </TuiTableBody>
            </div>
          </FlexPort>
        ) : (
          <TuiTableBody
            keyboard={keyboard}
            layout={layout}
            columns={columns}
            onRowSelect={onRowSelect}
            menuRenderer={menuRenderer}
            detailRenderer={detailRenderer}
          >
            {children}
          </TuiTableBody>
        ))}
    </TableRoot>
  );
};

export default TuiTable;
