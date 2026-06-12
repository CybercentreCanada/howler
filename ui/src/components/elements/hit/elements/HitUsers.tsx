import { avatarClasses, AvatarGroup, Chip, Divider, Stack, Typography } from '@mui/material';
import { useAppUser } from 'commons/components/app/hooks';
import HowlerAvatar from 'components/elements/display/HowlerAvatar';
import type { Hit } from 'models/entities/generated/Hit';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { HitLayout } from '../HitLayout';

type AssignedProps = FC<{
  hit: Hit;
  layout: HitLayout;
  hideLabel?: boolean;
  showAssigned?: boolean;
  showAssessor?: boolean;
}>;

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
const HitUsers: AssignedProps = ({ hit, layout, hideLabel = false, showAssigned = false, showAssessor = false }) => {
  const { t } = useTranslation();
  const { user } = useAppUser<HowlerUser>();

  const assessorVisible = showAssessor || hit.howler.assessment != null;
  const assigneeVisible = !hit.howler.assessor && (showAssigned || hit.howler.assignment !== 'unassigned');

  return (
    <Stack direction={hideLabel ? 'row' : 'column'} spacing={0.5} alignItems="flex-start">
      <Stack display="grid" gridTemplateColumns="repeat(2, 1fr)" alignItems="center" columnGap={0.5} rowGap={0.25}>
        {assigneeVisible && (
          <>
            {!hideLabel && <Typography variant="caption">{t('app.drawer.hit.assignment.assignee')}:</Typography>}
            <AvatarChip
              userId={hit?.howler.assignment}
              noUser="unassigned"
              placeholder={t('app.drawer.hit.assignment.unassigned.name')}
              layout={layout}
              hideLabel={hideLabel}
            />
          </>
        )}
        {assessorVisible && (
          <>
            {!hideLabel && <Typography variant="caption">{t('app.drawer.hit.assessment.assessor')}:</Typography>}
            <AvatarChip
              userId={hit.howler.assessor}
              noUser="unknown"
              placeholder={t('app.drawer.hit.assessment.unknown.name')}
              layout={layout}
              hideLabel={hideLabel}
            />
          </>
        )}
      </Stack>
      {hit.howler.viewers?.length > 0 && hideLabel && <Divider orientation="vertical" flexItem variant="middle" />}
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
        {[...new Set(hit?.howler.viewers)]
          .filter(viewer => viewer !== user.username)
          .map(viewer => (
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

export default HitUsers;
