import { avatarClasses, AvatarGroup, Chip, Stack } from '@mui/material';
import { useAppUser } from 'commons/components/app/hooks';
import { SocketContext } from 'components/app/providers/SocketProvider';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { HitLayout } from '../HitLayout';

const Assigned: FC<{ hit: Hit; layout: HitLayout; hideLabel?: boolean }> = ({ hit, layout, hideLabel = false }) => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const { viewers } = useContext(SocketContext);

  const hitViewers = uniq(viewers[hit?.howler?.id] ?? []).filter(viewer => viewer !== user.username);

  const userAvatar = (
    <HowlerAvatar
      userId={hit.howler.assignment}
      sx={{ height: layout !== HitLayout.COMFY ? 24 : 32, width: layout !== HitLayout.COMFY ? 24 : 32 }}
    />
  );

  return (
    <Stack direction="row" spacing={0.5}>
      {hideLabel ? (
        userAvatar
      ) : (
        <Chip
          variant="outlined"
          sx={{
            width: 'fit-content',
            '& .MuiChip-icon': {
              marginLeft: 0
            }
          }}
          icon={userAvatar}
          label={
            !hideLabel &&
            (hit?.howler.assignment !== 'unassigned'
              ? hit?.howler.assignment
              : t('app.drawer.hit.assignment.unassigned.name'))
          }
          size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
        />
      )}
      <AvatarGroup
        max={3}
        sx={{ [`.${avatarClasses.root}`]: { border: 0, marginLeft: 0.5 } }}
        componentsProps={{
          additionalAvatar: {
            sx: {
              height: layout !== HitLayout.COMFY ? 24 : 32,
              width: layout !== HitLayout.COMFY ? 24 : 32,
              fontSize: '12px'
            }
          }
        }}
      >
        {hitViewers.map(viewer => (
          <HowlerAvatar
            key={viewer}
            userId={viewer}
            sx={{ height: layout !== HitLayout.COMFY ? 24 : 32, width: layout !== HitLayout.COMFY ? 24 : 32 }}
          />
        ))}
      </AvatarGroup>
    </Stack>
  );
};

export default Assigned;
