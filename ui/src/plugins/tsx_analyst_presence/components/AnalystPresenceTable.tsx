import { ExpandLess as ExpandLessIcon, ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import { TsxColoredDot } from 'plugins/tsx_components/tsx_colored_dot';
import { useSharedUserStatusList } from 'plugins/tsx_hooks/user_status/UserStatusListContext';
import { Fragment, useCallback, useMemo, useState, type ComponentProps } from 'react';
import { useTranslation } from 'react-i18next';
import { useAnalystPresenceFilters } from '../hooks/useAnalystPresenceFilters';
import {
  enrichUserStatusResponse,
  filterByKeyword,
  filterByStatus,
  filterByTags,
  sortUsersByStatus,
  type AnalystUser
} from '../utils';
import { AnalystPresenceTableDetails } from './AnalystPresenceTableDetails';

type AnalystPresenceTableProps = {
  keyword: string;
};

const COLUMN_COUNT = 6;

const getStatusDotColor = (status: AnalystUser['status']): ComponentProps<typeof TsxColoredDot>['color'] | null => {
  if (status === 'available') return 'green';
  if (status === 'away') return 'yellow';
  if (status === 'busy') return 'red';
  if (status === 'unavailable') return 'gray';
  return null;
};

export const AnalystPresenceTable = ({ keyword }: AnalystPresenceTableProps) => {
  const { t } = useTranslation();
  const { activeStatusFilter, activeTagFilters } = useAnalystPresenceFilters();

  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = useCallback((uname: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(uname)) {
        next.delete(uname);
      } else {
        next.add(uname);
      }
      return next;
    });
  }, []);

  const { data: users, isLoading: isLoadingUsers, isError: isUsersError } = useSharedUserStatusList();
  const enrichedUsers = useMemo(() => enrichUserStatusResponse(users ?? []), [users]);
  const sortedUsers = useMemo(() => sortUsersByStatus(enrichedUsers), [enrichedUsers]);

  const filteredUsers = useMemo(() => {
    let result = sortedUsers;

    if (activeStatusFilter !== 'all') {
      result = filterByStatus(result, activeStatusFilter);
    }

    if (keyword.trim() !== '') {
      result = filterByKeyword(result, keyword);
    }

    if (
      activeTagFilters.portfolio.length > 0 ||
      activeTagFilters.products.length > 0 ||
      activeTagFilters.primary_disciplines.length > 0
    ) {
      result = filterByTags(result, activeTagFilters);
    }

    return result;
  }, [sortedUsers, keyword, activeStatusFilter, activeTagFilters]);

  if (!users && isLoadingUsers) {
    return <CircularProgress size={24} sx={{ display: 'block', mx: 'auto' }} />;
  }

  if (!users && isUsersError) {
    return (
      <Alert severity="error" sx={{ mt: 2, mx: 2 }}>
        {t('tsxAnalystPresence.error.status.fetch')}
      </Alert>
    );
  }

  return (
    <TableContainer sx={{ mx: 2, mb: 2, width: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: 48 }} />
            <TableCell>{t('tsxAnalystPresence.table.header.name')}</TableCell>
            <TableCell>{t('tsxAnalystPresence.table.header.team')}</TableCell>
            <TableCell>{t('tsxAnalystPresence.table.header.shift')}</TableCell>
            <TableCell>{t('tsxAnalystPresence.table.header.tags')}</TableCell>
            <TableCell>{t('tsxAnalystPresence.table.header.status')}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filteredUsers.length === 0 ? (
            <TableRow>
              <TableCell colSpan={COLUMN_COUNT} align="center" sx={{ color: 'text.secondary', border: 0, py: 4 }}>
                {t('tsxAnalystPresence.filter.noResults')}
              </TableCell>
            </TableRow>
          ) : (
            filteredUsers.map(row => {
              const isExpanded = expandedRows.has(row.uname);
              const isUnavailable = row.status === null;
              const dotColor = getStatusDotColor(row.status);

              return (
                <Fragment key={row.uname}>
                  <TableRow
                    hover
                    sx={{
                      ...(isUnavailable && { '& > .MuiTableCell-root': { color: 'text.secondary' } }),
                      ...(isExpanded && { '& > .MuiTableCell-root': { borderBottom: 'none' } })
                    }}
                  >
                    <TableCell>
                      <IconButton
                        size="small"
                        aria-label={isExpanded ? t('tsxAnalystPresence.table.collapse') : t('tsxAnalystPresence.table.expand')}
                        onClick={() => toggleRow(row.uname)}
                      >
                        {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                      </IconButton>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.name}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.team}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.schedule}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{row.totalTagsCount > 0 ? row.totalTagsCount : ''}</Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {dotColor && <TsxColoredDot color={dotColor} variant="ghost" />}
                        <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                          {row.status}
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell colSpan={COLUMN_COUNT} sx={{ py: 0, border: 0 }}>
                      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
                        <AnalystPresenceTableDetails user={row} />
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </Fragment>
              );
            })
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
