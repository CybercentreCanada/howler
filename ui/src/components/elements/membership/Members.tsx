import { AvatarGroup } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import HowlerAvatar from '../display/HowlerAvatar';
import type { Ownership } from './types';
import { getAllMembers } from './utils';

const Members: FC<{ item: Ownership }> = ({ item }) => {
  const { t } = useTranslation();

  return (
    <AvatarGroup
      max={5}
      slotProps={{
        surplus: {
          sx: { height: 32, width: 32, fontSize: '12px' }
        }
      }}
    >
      {getAllMembers(item).map(([member, privilege]) => (
        <HowlerAvatar
          key={member}
          userId={member}
          label={t(`membership.privilege.${privilege}`) + ' - ' + member}
          sx={{ height: 32, width: 32 }}
        />
      ))}
    </AvatarGroup>
  );
};

export default Members;
