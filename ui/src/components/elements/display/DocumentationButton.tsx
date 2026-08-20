import { Help } from '@mui/icons-material';
import { IconButton, Tooltip } from '@mui/material';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';

const DocumentationButton: FC = () => {
  const { t } = useTranslation();
  const location = useLocation();

  const [link, i18nKey] = useMemo(() => {
    if (location.pathname === '/advanced') {
      return ['/help/advanced', 'documentation.open.advanced'];
    }

    if (location.pathname === '/cases' || location.pathname.startsWith('/cases/')) {
      return ['/help/cases', 'documentation.open.cases'];
    }

    if (location.pathname === '/dossiers' || location.pathname.startsWith('/dossiers/')) {
      return ['/help/dossiers', 'documentation.open.dossiers'];
    }

    switch (location.pathname) {
      case '/action': {
        return ['/help/actions', 'documentation.open.actions'];
      }
      case '/search':
        return ['/help/search', 'documentation.open.search'];
      case '/views':
      case '/views/create': {
        return ['/help/views', 'documentation.open.views'];
      }
      case '/templates':
      case '/templates/view': {
        return ['/help/templates', 'documentation.open.templates'];
      }
      default: {
        return [null, null];
      }
    }
  }, [location.pathname]);

  return (
    link && (
      <Tooltip title={t(i18nKey)}>
        <IconButton size="small" component={Link} to={link} sx={{ ml: -2, color: 'text.secondary', opacity: 0.8 }}>
          <Help sx={{ fontSize: '16px' }} />
        </IconButton>
      </Tooltip>
    )
  );
};

export default DocumentationButton;
