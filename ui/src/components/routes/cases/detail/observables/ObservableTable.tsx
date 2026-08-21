import {
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography
} from '@mui/material';
import ChipPopper from 'components/elements/display/ChipPopper';
import PluginTypography from 'components/elements/PluginTypography';
import type { Case } from 'models/entities/generated/Case';
import { memo, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import { ESCALATION_COLORS } from 'utils/constants';
import type { ObservableEntry, ObservableRole } from '../types';

const ROLE_COLORS: Record<ObservableRole, 'error' | 'warning' | 'info'> = {
  threat: 'error',
  target: 'warning',
  indicator: 'info'
};

type SortColumn = 'type' | 'value' | 'role' | 'seen_in' | 'escalation';
type SortDirection = 'asc' | 'desc';

const getSortValue = (observable: ObservableEntry, column: SortColumn): string | number => {
  switch (column) {
    case 'type':
      return observable.type;
    case 'value':
      return observable.value.toLowerCase();
    case 'role':
      return observable.role ?? '';
    case 'seen_in':
      return observable.sources?.length ?? 0;
    case 'escalation':
      return (observable.sources ?? [])
        .map(s => s.escalation)
        .filter(Boolean)
        .join(',');
    default:
      return '';
  }
};

const ObservableTable: FC<{ observables: ObservableEntry[]; case: Case }> = ({ observables, case: _case }) => {
  const { t } = useTranslation();
  const [sortColumn, setSortColumn] = useState<SortColumn>('type');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSortDirection(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  const sortedObservables = useMemo(() => {
    return [...observables].sort((a, b) => {
      const aVal = getSortValue(a, sortColumn);
      const bVal = getSortValue(b, sortColumn);
      const cmp =
        typeof aVal === 'number' && typeof bVal === 'number' ? aVal - bVal : String(aVal).localeCompare(String(bVal));
      return sortDirection === 'asc' ? cmp : -cmp;
    });
  }, [observables, sortColumn, sortDirection]);

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sortDirection={sortColumn === 'type' ? sortDirection : false}>
              <TableSortLabel
                active={sortColumn === 'type'}
                direction={sortColumn === 'type' ? sortDirection : 'asc'}
                onClick={() => handleSort('type')}
              >
                {t('page.cases.observables.columns.type')}
              </TableSortLabel>
            </TableCell>
            <TableCell sortDirection={sortColumn === 'value' ? sortDirection : false}>
              <TableSortLabel
                active={sortColumn === 'value'}
                direction={sortColumn === 'value' ? sortDirection : 'asc'}
                onClick={() => handleSort('value')}
              >
                {t('page.cases.observables.columns.value')}
              </TableSortLabel>
            </TableCell>
            <TableCell sortDirection={sortColumn === 'role' ? sortDirection : false}>
              <TableSortLabel
                active={sortColumn === 'role'}
                direction={sortColumn === 'role' ? sortDirection : 'asc'}
                onClick={() => handleSort('role')}
              >
                {t('page.cases.observables.columns.role')}
              </TableSortLabel>
            </TableCell>
            <TableCell align="right" sortDirection={sortColumn === 'seen_in' ? sortDirection : false}>
              <TableSortLabel
                active={sortColumn === 'seen_in'}
                direction={sortColumn === 'seen_in' ? sortDirection : 'asc'}
                onClick={() => handleSort('seen_in')}
              >
                {t('page.cases.observables.columns.seen_in')}
              </TableSortLabel>
            </TableCell>
            <TableCell>{t('page.cases.observables.columns.sources')}</TableCell>
            <TableCell sortDirection={sortColumn === 'escalation' ? sortDirection : false}>
              <TableSortLabel
                active={sortColumn === 'escalation'}
                direction={sortColumn === 'escalation' ? sortDirection : 'asc'}
                onClick={() => handleSort('escalation')}
              >
                {t('page.cases.observables.columns.escalation')}
              </TableSortLabel>
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedObservables.map(observable => {
            const sources = observable.sources ?? [];
            const escalations = [...new Set(sources.map(s => s.escalation).filter(Boolean))];
            const linkedSources = sources.filter(source => source.path);

            return (
              <TableRow key={`${observable.type}:${observable.value}`}>
                <TableCell>
                  <Chip
                    size="small"
                    label={t(`page.cases.observables.type.${observable.type}`)}
                    color="primary"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell sx={{ maxWidth: 300 }}>
                  <PluginTypography
                    value={observable.value}
                    context="table"
                    variant="body2"
                    sx={{ fontFamily: 'monospace', wordBreak: 'break-all' }}
                  />
                </TableCell>
                <TableCell>
                  {observable.role && (
                    <Chip
                      size="small"
                      label={t(`page.cases.observables.role.${observable.role}`)}
                      color={ROLE_COLORS[observable.role]}
                      variant="outlined"
                    />
                  )}
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2">{sources.length}</Typography>
                </TableCell>
                <TableCell>
                  {linkedSources.length === 0 ? null : linkedSources.length === 1 ? (
                    <Chip
                      clickable
                      size="small"
                      label={linkedSources[0].label ?? linkedSources[0].path}
                      variant="outlined"
                      component={Link}
                      to={`/cases/${_case.case_id}/${linkedSources[0].path}`}
                    />
                  ) : (
                    <ChipPopper
                      label={`${linkedSources[0].label ?? linkedSources[0].path} (+${linkedSources.length - 1})`}
                      slotProps={{ chip: { size: 'small', variant: 'outlined' } }}
                    >
                      <Stack gap={0.5}>
                        {linkedSources.map(source => (
                          <Chip
                            key={source.id}
                            clickable
                            size="small"
                            label={source.label ?? source.path}
                            variant="outlined"
                            component={Link}
                            to={`/cases/${_case.case_id}/${source.path}`}
                          />
                        ))}
                      </Stack>
                    </ChipPopper>
                  )}
                </TableCell>
                <TableCell>
                  <Stack direction="row" flexWrap="wrap" gap={0.5}>
                    {escalations.map(esc => (
                      <Chip
                        key={esc}
                        size="small"
                        label={esc}
                        color={ESCALATION_COLORS[esc as keyof typeof ESCALATION_COLORS] ?? 'default'}
                      />
                    ))}
                  </Stack>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default memo(ObservableTable);
