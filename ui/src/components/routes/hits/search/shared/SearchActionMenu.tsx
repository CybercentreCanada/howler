import { SavedSearch, Terminal } from '@mui/icons-material';
import { IconButton, Stack, Tooltip } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';
import LayoutSettings from './LayoutSettings';

const SearchActionMenu = ({ query }: { query: string }) => {
  const { t } = useTranslation();

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Tooltip title={t('route.views.save')}>
        <IconButton component={Link} disabled={!query} to={`/views/create?query=${query}`}>
          <SavedSearch />
        </IconButton>
      </Tooltip>
      <Tooltip title={t('route.actions.save')}>
        <IconButton component={Link} disabled={!query} to={`/action/execute?query=${query}`}>
          <Terminal />
        </IconButton>
      </Tooltip>
      <LayoutSettings />
    </Stack>
  );
};

export default SearchActionMenu;
