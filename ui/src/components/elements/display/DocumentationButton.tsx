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
    switch (location.pathname) {
      case '/action': {
        return ['/help/actions', 'documentation.open.actions'];
      }
      case '/search':
      case '/advanced': {
        return ['/help/search', 'documentation.open.search'];
      }
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
