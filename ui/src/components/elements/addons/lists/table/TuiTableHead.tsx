import { VSBoxContext } from 'components/elements/addons/layout/vsbox/VSBox';
import { useContext } from 'react';
import type { TuiTableColumn } from '.';
import TuiTableHeader from './TuiTableHeader';
import type TuiTableLayout from './TuiTableLayout';

type TuiTableHeaderProps = {
  layout: TuiTableLayout;
  columns: TuiTableColumn[];
};

const TuiTableHead = ({ layout, columns }: TuiTableHeaderProps) => {
  const {
    state: { scrollTop }
  } = useContext(VSBoxContext);
  return (
    <div
      data-tuitable-header="true"
      className="tui-table-head tui-table-divider"
      style={{ position: scrollTop ? 'sticky' : null, top: scrollTop || null }}
    >
      {columns.map(column => (
        <TuiTableHeader key={column.column} width={layout.getWidth(column.column, true)} column={column} />
      ))}
    </div>
  );
};

export default TuiTableHead;
