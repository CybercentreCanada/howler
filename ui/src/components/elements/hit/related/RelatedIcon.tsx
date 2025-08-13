import { Icon, iconExists } from '@iconify/react/dist/iconify.js';
import Avatar from '@mui/material/Avatar';
import { useAppTheme } from 'commons/components/app/hooks';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { useContext, type FC } from 'react';

const RelatedIcon: FC<{ icon?: string; title?: string; href?: string; compact?: boolean }> = ({
  icon,
  title,
  href,
  compact = false
}) => {
  const { config } = useContext(ApiConfigContext);
  const { isDark } = useAppTheme();

  if (!icon) {
    return null;
  }

  if (iconExists(icon)) {
    return <Icon fontSize="1.5rem" icon={icon} />;
  }

  const app = config.configuration.ui.apps.find(a => a.name.toLowerCase() === icon?.toLowerCase());
  if (app) {
    // use the image link for the configured related application instead
    icon = app[`img_${isDark ? 'd' : 'l'}`];
  }

  return (
    <Avatar
      variant="rounded"
      alt={title ?? href}
      src={icon}
      sx={[
        theme => ({
          width: theme.spacing(compact ? 4 : 6),
          height: theme.spacing(compact ? 4 : 6),
          '& img': {
            objectFit: 'contain'
          }
        }),
        !icon && { backgroundColor: 'transparent' }
      ]}
    >
      {icon}
    </Avatar>
  );
};

export default RelatedIcon;
