import { Close as CloseIcon } from '@mui/icons-material';
import Box from '@mui/material/Box';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useCallback, useRef, useState, type ComponentProps, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { AnalystPresenceFiltersProvider } from '../context/AnalystPresenceFiltersProvider';
import { AnalystPresenceSnackbarProvider } from '../context/AnalystPresenceSnackbarProvider';
import { AnalystPresenceDrawerFilters } from './AnalystPresenceDrawerFilters';
import { AnalystPresenceSnackbar } from './AnalystPresenceSnackbar';
import { AnalystPresenceTable } from './AnalystPresenceTable';

type AnalystPresenceDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
};

type DrawerOnCloseReason = Parameters<NonNullable<ComponentProps<typeof Drawer>['onClose']>>[1];

export const AnalystPresenceDrawer = ({ isOpen, onClose }: AnalystPresenceDrawerProps) => {
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { t } = useTranslation();

  const [keyword, setKeyword] = useState('');

  const handleSearchKeyDown = useCallback((event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape') {
      return;
    }

    event.stopPropagation();
    setKeyword('');
  }, []);

  const handleClose = useCallback(
    (reason: DrawerOnCloseReason) => {
      const isSearchInputFocused = searchInputRef.current === document.activeElement;
      if (reason === 'escapeKeyDown' && isSearchInputFocused) {
        return;
      }

      onClose();
    },
    [onClose]
  );

  return (
    <AnalystPresenceSnackbarProvider>
      <Drawer
        anchor="right"
        open={isOpen}
        onClose={(_, reason) => handleClose(reason)}
        aria-labelledby="analyst-presence-drawer-title"
        sx={{ '& .MuiDrawer-paper': { width: 720 } }}
      >
        <Stack sx={{ height: '100%' }}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              py: 1.5,
              pl: 3,
              pr: 1.5,
              borderBottom: '1px solid',
              borderColor: 'divider'
            }}
          >
            <Typography id="analyst-presence-drawer-title" variant="h6">
              {t('tsxAnalystPresence.common.analysts')}
            </Typography>
            <IconButton size="small" onClick={onClose} aria-label={t('tsxAnalystPresence.common.close')}>
              <CloseIcon />
            </IconButton>
          </Box>

          <TextField
            inputRef={searchInputRef}
            size="small"
            variant="outlined"
            label={t('tsxAnalystPresence.filter.search')}
            placeholder={t('tsxAnalystPresence.filter.search.placeholder')}
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            autoComplete="off"
            sx={{ mt: 3, mx: 2 }}
          />

          <AnalystPresenceFiltersProvider>
            <AnalystPresenceDrawerFilters />

            <AnalystPresenceTable keyword={keyword} />
          </AnalystPresenceFiltersProvider>
        </Stack>

        <AnalystPresenceSnackbar />
      </Drawer>
    </AnalystPresenceSnackbarProvider>
  );
};
