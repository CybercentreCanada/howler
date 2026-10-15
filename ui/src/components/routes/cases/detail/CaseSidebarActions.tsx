import { AddCircle, Description, Event as EventIcon, Folder, Refresh, UnfoldLess } from '@mui/icons-material';
import { Card, IconButton, Stack, Tooltip, useTheme } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

interface CaseSidebarActionsProps {
  onAddEvent: () => void;
  onAddItem: () => void;
  onAddFolder: () => void;
  onRefresh: () => void;
  onCollapseAll: () => void;
}

const CaseSidebarActions: FC<CaseSidebarActionsProps> = ({
  onAddEvent,
  onAddItem,
  onAddFolder,
  onRefresh,
  onCollapseAll
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const addIconSx = {
    fontSize: '12px',
    position: 'absolute',
    bottom: 2,
    right: 2,
    backgroundColor: theme.palette.background.paper,
    borderRadius: '100%'
  };

  return (
    <Card sx={{ borderRadius: 0, p: 0.25 }}>
      <Stack direction="row" spacing={0.25}>
        <div style={{ flex: 1 }} />
        <Tooltip title={t('page.cases.sidebar.add_event')}>
          <IconButton size="small" sx={{ position: 'relative' }} onClick={onAddEvent}>
            <EventIcon sx={{ fontSize: '18px' }} />
            <AddCircle sx={addIconSx} htmlColor="grey" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('page.cases.sidebar.add_item')}>
          <IconButton size="small" sx={{ position: 'relative' }} onClick={onAddItem}>
            <Description sx={{ fontSize: '18px' }} />
            <AddCircle sx={addIconSx} htmlColor="grey" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('page.cases.sidebar.add_folder')}>
          <IconButton size="small" sx={{ position: 'relative' }} onClick={onAddFolder}>
            <Folder sx={{ fontSize: '18px' }} />
            <AddCircle sx={addIconSx} htmlColor="grey" />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('page.cases.sidebar.refresh')}>
          <IconButton size="small" onClick={onRefresh}>
            <Refresh sx={{ fontSize: '18px' }} />
          </IconButton>
        </Tooltip>
        <Tooltip title={t('page.cases.sidebar.collapse_all')}>
          <IconButton size="small" onClick={onCollapseAll}>
            <UnfoldLess sx={{ fontSize: '18px' }} />
          </IconButton>
        </Tooltip>
      </Stack>
    </Card>
  );
};

export default CaseSidebarActions;
