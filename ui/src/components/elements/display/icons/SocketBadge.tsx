import { CloudSync } from '@mui/icons-material';
import { Badge, IconButton, styled, Tooltip } from '@mui/material';
import { green, red, yellow } from '@mui/material/colors';
import { SocketContext, Status } from 'components/app/providers/SocketProvider';
import i18n from 'i18n';
import type { FC } from 'react';
import { useContext } from 'react';

const StyledBadge = styled(Badge)(({ theme }) => ({
  '& .MuiBadge-badge': {
    backgroundColor: green[700],
    color: green[700],
    boxShadow: `0 0 0 2px ${theme.palette.background.paper}`,
    '&::after': {
      position: 'absolute',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      borderRadius: '50%',
      animation: 'ripple 1.2s infinite ease-in-out',
      border: '1px solid currentColor',
      content: '""',
      zIndex: 1000
    }
  },
  '@keyframes ripple': {
    '0%': {
      transform: 'scale(.8)',
      opacity: 1
    },
    '100%': {
      transform: 'scale(2.4)',
      opacity: 0
    }
  }
}));

const TITLES = {
  [Status.CONNECTING]: i18n.t('live.connecting'),
  [Status.OPEN]: i18n.t('live.open'),
  [Status.CLOSING]: i18n.t('live.closing'),
  [Status.CLOSED]: i18n.t('live.closed')
};

const SocketBadge: FC<{ size?: 'small' | 'inherit' | 'medium' | 'large' }> = ({ size = 'inherit' }) => {
  const { status, reconnect } = useContext(SocketContext);

  return (
    <Tooltip title={TITLES[status]}>
      <StyledBadge
        overlap="circular"
        variant="dot"
        anchorOrigin={{ horizontal: 'left', vertical: 'top' }}
        sx={[
          (status === Status.CONNECTING || status === Status.CLOSING) && {
            '& .MuiBadge-badge': { backgroundColor: yellow[600], color: yellow[600] }
          },
          status === Status.CLOSED && {
            '& .MuiBadge-badge': {
              backgroundColor: red[800],
              color: red[800],
              '&::after': {
                animation: 'none'
              }
            }
          }
        ]}
      >
        <IconButton
          size="small"
          onClick={reconnect}
          sx={[status !== Status.CLOSED && { pointerEvents: 'none' }, { pr: 1 }]}
        >
          <CloudSync fontSize={size} />
        </IconButton>
      </StyledBadge>
    </Tooltip>
  );
};

export default SocketBadge;
