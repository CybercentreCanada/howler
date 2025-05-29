import { Avatar, Stack, Typography } from '@mui/material';
import { useAppTheme } from 'commons/components/app/hooks';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import HowlerCard from 'components/elements/display/HowlerCard';
import React, { useContext, useMemo, type PropsWithChildren } from 'react';
import { Link } from 'react-router-dom';

const RelatedLink: React.FC<PropsWithChildren<{ icon?: string; title?: string; href?: string; compact?: boolean }>> = ({
  icon,
  title,
  href,
  compact = false,
  children
}) => {
  const { config } = useContext(ApiConfigContext);
  const { isDark } = useAppTheme();

  const _icon = useMemo(() => {
    if (icon) {
      const app = config.configuration.ui.apps.find(a => a.name.toLowerCase() === icon?.toLowerCase());
      if (app) {
        return app[`img_${isDark ? 'd' : 'l'}`];
      }
    }

    return icon;
  }, [config.configuration.ui.apps, icon, isDark]);

  return (
    <HowlerCard
      variant={compact ? 'outlined' : 'elevation'}
      key={href}
      onClick={() => window.open(href)}
      sx={[
        theme => ({
          cursor: 'pointer',
          backgroundColor: 'transparent',
          transition: theme.transitions.create(['border-color']),
          '&:hover': { borderColor: 'primary.main', '& a': { textDecoration: 'underline' } },
          '& > div': {
            height: '100%'
          },
          '& a': { textDecoration: 'none', color: 'text.primary' }
        }),
        !compact && { border: 'thin solid', borderColor: 'transparent' }
      ]}
    >
      <Stack direction="row" p={compact ? 0.5 : 1} spacing={1} alignItems="center">
        {children || (
          <Avatar
            variant="rounded"
            alt={title ?? href}
            src={_icon}
            sx={[
              theme => ({
                width: theme.spacing(compact ? 4 : 6),
                height: theme.spacing(compact ? 4 : 6),
                '& img': {
                  objectFit: 'contain'
                }
              }),
              !_icon && { backgroundColor: 'transparent' }
            ]}
          >
            {_icon}
          </Avatar>
        )}
        <Typography component={Link} to={href} onClick={e => e.stopPropagation()}>
          {title ?? href}
        </Typography>
      </Stack>
    </HowlerCard>
  );
};

export default RelatedLink;
