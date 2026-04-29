import { KeyboardArrowUp } from '@mui/icons-material';
import { Box, Collapse, IconButton, lighten, Stack, TableCell, TableRow, Typography, useTheme } from '@mui/material';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import Assigned from 'components/elements/hit/elements/Assigned';
import EscalationChip from 'components/elements/hit/elements/EscalationChip';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import ObservableCard from 'components/elements/observable/ObservableCard';
import { get } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { Observable } from 'models/entities/generated/Observable';
import { memo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { isHit } from 'utils/typeUtils';
import EnhancedCell from './EnhancedCell';

const RecordRow: FC<{
  record: Hit | Observable;
  analyticIds: Record<string, string>;
  columns: string[];
  columnWidths: Record<string, string>;
  collapseMainColumn: boolean;
  onClick: (e: React.MouseEvent<HTMLDivElement>, record: Hit | Observable) => void;
}> = ({ record, analyticIds, columns, columnWidths, collapseMainColumn, onClick }) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const selectedHits = useContextSelector(RecordContext, ctx => ctx.selectedRecords);

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const [expandRow, setExpandRow] = useState(false);

  return (
    <>
      <TableRow
        key={record.howler.id}
        id={record.howler.id}
        onClick={ev => onClick(ev, record)}
        sx={[
          {
            transition: theme.transitions.create('background-color'),
            '&:hover': {
              cursor: 'pointer',
              backgroundColor: theme.palette.background.paper
            }
          },
          selectedHits.some(_hit => _hit.howler.id === record.howler.id) && {
            backgroundColor: lighten(theme.palette.background.paper, 0.15)
          },
          selected === record.howler.id && {
            backgroundColor: lighten(theme.palette.background.paper, 0.25)
          }
        ]}
      >
        <TableCell
          sx={{
            borderBottom: 'none',
            borderRight: 'thin solid',
            borderRightColor: 'divider',
            '& a': { color: 'text.primary' }
          }}
        >
          <Stack direction="row" spacing={1} alignItems="center">
            <IconButton
              size="small"
              sx={[
                { transform: 'rotate(0)', transition: theme.transitions.create('transform') },
                expandRow && { transform: 'rotate(180deg)' }
              ]}
              onClick={e => {
                e.preventDefault();
                e.stopPropagation();
                setExpandRow(_expanded => !_expanded);
              }}
            >
              <KeyboardArrowUp />
            </IconButton>
            <Collapse in={!collapseMainColumn} orientation="horizontal" unmountOnExit>
              <Stack direction="row" spacing={1} flexWrap="nowrap">
                {isHit(record) && <EscalationChip hit={record} layout={HitLayout.DENSE} hideLabel />}
                <Typography sx={{ textWrap: 'nowrap', whiteSpace: 'nowrap', fontSize: 'inherit' }}>
                  {analyticIds[record.howler.analytic] ? (
                    <Link to={`/analytics/${analyticIds[record.howler.analytic]}`} onClick={e => e.stopPropagation()}>
                      {record.howler.analytic}
                    </Link>
                  ) : (
                    record.howler.analytic
                  )}
                  {record.howler.detection && ': '}
                  {record.howler.detection}
                </Typography>
                {isHit(record) && record.howler.assignment !== 'unassigned' && (
                  <Assigned hit={record} layout={HitLayout.DENSE} hideLabel />
                )}
              </Stack>
            </Collapse>
          </Stack>
        </TableCell>
        {columns.map(col => (
          <EnhancedCell
            record={record}
            className={`col-${col.replaceAll('.', '-')}`}
            key={col}
            value={get(record, col) ?? t('none')}
            sx={columnWidths[col] ? { width: columnWidths[col] } : { width: '220px', maxWidth: '300px' }}
            field={col}
          />
        ))}
      </TableRow>
      <TableRow onClick={ev => onClick(ev, record)}>
        <TableCell colSpan={columns.length + 2} style={{ paddingBottom: 0, paddingTop: 0 }}>
          <Collapse in={expandRow} unmountOnExit>
            <Box width="100%" maxWidth="1200px" margin={1}>
              {isHit(record) ? (
                <HitCard id={record.howler.id} layout={HitLayout.NORMAL} />
              ) : (
                <ObservableCard id={record.howler.id} observable={record} />
              )}
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

export default memo(RecordRow);
