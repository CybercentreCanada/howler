import { KeyboardArrowUp } from '@mui/icons-material';
import { Box, Collapse, IconButton, lighten, Stack, TableCell, TableRow, Typography, useTheme } from '@mui/material';
import { HitContext } from 'components/app/providers/HitProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import Assigned from 'components/elements/hit/elements/Assigned';
import EscalationChip from 'components/elements/hit/elements/EscalationChip';
import HitCard from 'components/elements/hit/HitCard';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { get } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import EnhancedCell from './EnhancedCell';

const HitRow: FC<{
  hit: Hit;
  analyticIds: Record<string, string>;
  columns: string[];
  columnWidths: Record<string, string>;
  collapseMainColumn: boolean;
  onClick: (e: React.MouseEvent<HTMLDivElement>, hit: Hit) => void;
}> = ({ hit, analyticIds, columns, columnWidths, collapseMainColumn, onClick }) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const selected = useContextSelector(ParameterContext, ctx => ctx.selected);

  const [expandRow, setExpandRow] = useState(false);

  return (
    <>
      <TableRow
        key={hit.howler.id}
        id={hit.howler.id}
        onClick={ev => onClick(ev, hit)}
        sx={[
          {
            transition: theme.transitions.create('background-color'),
            '&:hover': {
              cursor: 'pointer',
              backgroundColor: theme.palette.background.paper
            }
          },
          selectedHits.some(_hit => _hit.howler.id === hit.howler.id) && {
            backgroundColor: lighten(theme.palette.background.paper, 0.15)
          },
          selected === hit.howler.id && {
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
                <EscalationChip hit={hit} layout={HitLayout.DENSE} hideLabel />
                <Typography sx={{ textWrap: 'nowrap', whiteSpace: 'nowrap', fontSize: 'inherit' }}>
                  {analyticIds[hit.howler.analytic] ? (
                    <Link to={`/analytics/${analyticIds[hit.howler.analytic]}`} onClick={e => e.stopPropagation()}>
                      {hit.howler.analytic}
                    </Link>
                  ) : (
                    hit.howler.analytic
                  )}
                  {hit.howler.detection && ': '}
                  {hit.howler.detection}
                </Typography>
                {hit.howler.assignment !== 'unassigned' && <Assigned hit={hit} layout={HitLayout.DENSE} hideLabel />}
              </Stack>
            </Collapse>
          </Stack>
        </TableCell>
        {columns.map(col => (
          <EnhancedCell
            hit={hit}
            className={`col-${col.replaceAll('.', '-')}`}
            key={col}
            value={get(hit, col) ?? t('none')}
            sx={columnWidths[col] ? { width: columnWidths[col] } : { width: '220px', maxWidth: '300px' }}
            field={col}
          />
        ))}
      </TableRow>
      <TableRow onClick={ev => onClick(ev, hit)}>
        <TableCell colSpan={columns.length + 2} style={{ paddingBottom: 0, paddingTop: 0 }}>
          <Collapse in={expandRow} unmountOnExit>
            <Box width="100%" maxWidth="1200px" margin={1}>
              <HitCard id={hit.howler.id} layout={HitLayout.NORMAL} />
            </Box>
          </Collapse>
        </TableCell>
      </TableRow>
    </>
  );
};

export default memo(HitRow);
