import { useAppUser } from '@tui/core';
import { avatarClasses, AvatarGroup, Chip, Divider, Stack } from '@mui/material';
import { SocketContext } from 'components/app/providers/SocketProvider';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import { uniq } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { HitLayout } from '../HitLayout';

type AvatarChipProps = {
  userId: string;
  noUser: string;
  placeholder: string;
  layout: HitLayout;
  hideLabel?: boolean;
};

const AvatarChip = ({ userId, noUser, placeholder, layout, hideLabel }: AvatarChipProps) => {
  const userAvatar = (
    <HowlerAvatar
      userId={userId}
      sx={{ height: layout !== HitLayout.COMFY ? 24 : 32, width: layout !== HitLayout.COMFY ? 24 : 32 }}
    />
  );

  return hideLabel ? (
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
      label={userId && userId !== noUser ? userId : placeholder}
      size={layout !== HitLayout.COMFY ? 'small' : 'medium'}
    />
  );
};

const Assigned: FC<{
  hit: Hit;
  layout: HitLayout;
  hideLabel?: boolean;
  showAssigned?: boolean;
}> = ({ hit, layout, hideLabel = false, showAssigned = false }) => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();
  const { viewers } = useContext(SocketContext);

  const hitViewers = uniq(viewers[hit?.howler?.id] ?? []).filter(viewer => viewer !== user.username);

  const assigneeVisible = showAssigned || hit.howler.assignment !== 'unassigned';

  return (
    <Stack direction="row" spacing={0.5}>
      {assigneeVisible && (
        <AvatarChip
          userId={hit?.howler.assignment}
          noUser="unassigned"
          placeholder={t('app.drawer.hit.assignment.unassigned.name')}
          layout={layout}
          hideLabel={hideLabel}
        />
      )}
      {hitViewers.length > 0 && hideLabel && <Divider orientation="vertical" flexItem variant="middle" />}
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
