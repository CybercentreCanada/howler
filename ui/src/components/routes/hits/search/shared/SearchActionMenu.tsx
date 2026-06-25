import { Close, SavedSearch, Terminal } from '@mui/icons-material';
import { IconButton, Stack, Tooltip } from '@mui/material';
import { HitContext } from 'components/app/providers/HitProvider';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import BundleParentMenu from './BundleParentMenu';
import LayoutSettings from './LayoutSettings';

const SearchActionMenu = ({ query }: { query: string }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const routeParams = useParams();

  const bundleHit = useContextSelector(HitContext, ctx =>
    location.pathname.startsWith('/bundles') ? ctx.hits[routeParams.id] : null
  );

  return (
    <Stack direction="row" spacing={1} alignItems="center">
      {bundleHit?.howler.bundles.length > 0 && <BundleParentMenu bundle={bundleHit} />}
      {bundleHit && (
        <Tooltip title={t('hit.bundle.close')}>
          <IconButton size="small" onClick={() => navigate('/search')}>
            <Close />
          </IconButton>
        </Tooltip>
      )}
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
