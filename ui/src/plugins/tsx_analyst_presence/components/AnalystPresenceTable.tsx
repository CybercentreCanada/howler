import { ExpandLess as ExpandLessIcon, ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import { DataGrid } from '@mui/x-data-grid';
import { TsxColoredDot } from 'plugins/tsx_components/tsx_colored_dot';
import { useSharedUserStatusList } from 'plugins/tsx_hooks/user_status/UserStatusListContext';
import { useMemo, type ComponentProps } from 'react';
import { useTranslation } from 'react-i18next';
import { useAnalystPresenceFilters } from '../hooks/useAnalystPresenceFilters';
import { enrichUserStatusResponse, filterByKeyword, filterByStatus, filterByTags, sortUsersByStatus } from '../utils';
import { AnalystPresenceTableDetails } from './AnalystPresenceTableDetails';

type AnalystPresenceTableProps = {
  keyword: string;
};

export const AnalystPresenceTable = ({ keyword }: AnalystPresenceTableProps) => {
  const { t } = useTranslation();
  const { activeStatusFilter, activeTagFilters } = useAnalystPresenceFilters();

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
    <DataGrid
      rows={filteredUsers}
      getRowId={row => row.uname}
      getRowClassName={({ row }) => (row.status === null ? 'analyst-presence-row-unavailable' : '')}
      disableColumnMenu
      disableColumnResize
      disableColumnSelector
      disableRowSelectionOnClick
      localeText={{ noRowsLabel: t('tsxAnalystPresence.filter.noResults') }}
      columns={[
        {
          field: 'name',
          headerName: t('tsxAnalystPresence.table.header.name'),
          flex: 1.5,
          renderCell: ({ row }) => {
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
                <Typography variant="body2">{row.name}</Typography>
              </Box>
            );
          }
        },
        {
          field: 'team',
          headerName: t('tsxAnalystPresence.table.header.team'),
          flex: 1,
          renderCell: ({ row }) => {
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
                <Typography variant="body2">{row.team}</Typography>
              </Box>
            );
          }
        },
        {
          field: 'schedule',
          headerName: t('tsxAnalystPresence.table.header.shift'),
          flex: 1,
          renderCell: ({ row }) => {
            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
                <Typography variant="body2">{row.schedule}</Typography>
              </Box>
            );
          }
        },
        {
          field: 'totalTagsCount',
          headerName: t('tsxAnalystPresence.table.header.tags'),
          renderCell: ({ row }) => (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography variant="body2">{row.totalTagsCount > 0 ? row.totalTagsCount : ''}</Typography>
            </Box>
          )
        },
        {
          field: 'status',
          headerName: t('tsxAnalystPresence.table.header.status'),
          flex: 1,
          renderCell: ({ row }) => {
            let dotColor: ComponentProps<typeof TsxColoredDot>['color'] | null = null;

            if (row.status === 'available') {
              dotColor = 'green';
            } else if (row.status === 'away') {
              dotColor = 'yellow';
            } else if (row.status === 'busy') {
              dotColor = 'red';
            } else if (row.status === 'unavailable') {
              dotColor = 'gray';
            }

            return (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, height: '100%' }}>
                {dotColor && <TsxColoredDot color={dotColor} variant="ghost" />}
                <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                  {row.status}
                </Typography>
              </Box>
            );
          }
        }
      ]}
      slots={{
        detailPanelExpandIcon: ({ color: _, ...props }) => <ExpandMoreIcon {...props} />,
        detailPanelCollapseIcon: ({ color: _, ...props }) => <ExpandLessIcon {...props} />
      }}
      getDetailPanelContent={({ row }) => <AnalystPresenceTableDetails user={row} />}
      sx={{
        mx: 2,
        mb: 2,
        '& .analyst-presence-row-unavailable .MuiDataGrid-cell': {
          color: 'text.secondary'
        },
        '& .MuiDataGrid-cell:focus, & .MuiDataGrid-cell:focus-within': {
          outline: 'none'
        },
        '& .MuiDataGrid-columnHeader:focus, & .MuiDataGrid-columnHeader:focus-within': {
          outline: 'none'
        }
      }}
    />
  );
};
