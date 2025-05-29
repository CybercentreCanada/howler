import type { AvatarProps, SxProps, Theme } from '@mui/material';
import { Avatar, Tooltip, useTheme } from '@mui/material';
import { AvatarContext } from 'components/app/providers/AvatarProvider';
import { memo, useCallback, useContext, useEffect, useState, type FC, type ReactNode } from 'react';
import { nameToInitials } from 'utils/stringUtils';
import { stringToColor } from 'utils/utils';

type HowlerAvatarProps = AvatarProps & {
  userId: string;
};

const HowlerAvatar: FC<HowlerAvatarProps> = ({ userId, ...avatarProps }) => {
  const { getAvatar } = useContext(AvatarContext);
  const theme = useTheme();
  const [props, setProps] = useState<{ sx?: SxProps<Theme>; children?: ReactNode | ReactNode[]; src?: string }>();

  const stringAvatar = useCallback(
    (name: string) => {
      return {
        sx: {
          bgcolor: stringToColor(name),
          color: theme.palette.getContrastText(stringToColor(name))
        },
        children: nameToInitials(name)
      };
    },
    [theme.palette]
  );

  useEffect(() => {
    if (!userId || userId.toLowerCase() === 'unassigned') {
      setProps({});
    } else {
      getAvatar(userId)
        .then(av =>
          av && !av.startsWith('http') && !av.startsWith('data:') ? setProps(stringAvatar(av)) : setProps({ src: av })
        )
        .catch(e => {
          // eslint-disable-next-line no-console
          console.debug(e);
          setProps({
            src: null
          });
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  if (userId) {
    return (
      <Tooltip title={userId}>
        <Avatar
          {...avatarProps}
          {...props}
          sx={{ ...(avatarProps?.sx || {}), ...(props?.sx || {}) } as SxProps<Theme>}
        />
      </Tooltip>
    );
  } else {
    return (
      <Avatar {...avatarProps} {...props} sx={{ ...(avatarProps?.sx || {}), ...(props?.sx || {}) } as SxProps<Theme>} />
    );
  }
};

export default memo(HowlerAvatar);
