import { Icon } from '@iconify/react';
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

  let avatarImage: string = null;
  const app = config.configuration.ui.apps.find(a => a.name.toLowerCase() === icon?.toLowerCase());
  if (app) {
    // use the image link for the configured related application instead
    avatarImage = app[`img_${isDark ? 'd' : 'l'}`];
  } else if (icon.startsWith('http')) {
    avatarImage = icon;
  }

  if (avatarImage) {
    return (
      <Avatar
        variant="rounded"
        alt={title ?? href}
        src={avatarImage}
        sx={[
          theme => ({
            width: theme.spacing(compact ? 4 : 6),
            height: theme.spacing(compact ? 4 : 6),
            '& img': {
              objectFit: 'contain'
            }
          }),
          !avatarImage && { backgroundColor: 'transparent' }
        ]}
      >
        {avatarImage}
      </Avatar>
    );
  }

  return <Icon fontSize="1.5rem" icon={icon} />;
};

export default RelatedIcon;
