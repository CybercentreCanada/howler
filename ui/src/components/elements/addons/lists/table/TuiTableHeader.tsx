import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import type { TuiTableColumn } from '.';

const TuiTableHeader = ({ width, column }: { width: number; column: TuiTableColumn }) => {
  const { t } = useTranslation();

  return (
    <div className="tui-table-header" style={{ minWidth: width }}>
      <div>{column.i18nKey ? t(column.i18nKey) : column.label}</div>
    </div>
  );
};

export default memo(TuiTableHeader);
