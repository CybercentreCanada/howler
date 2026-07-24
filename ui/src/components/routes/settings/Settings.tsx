import { useAppUser } from '@tui/core';
import UserPageWrapper from 'components/elements/display/UserPageWrapper';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMyUserFunctions from 'components/hooks/useMyUserFunctions';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useMemo, type FC } from 'react';
import { StorageKey } from 'utils/constants';
import AdminSection from './AdminSection';
import LocalSection from './LocalSection';
import ProfileSection from './ProfileSection';
import SecuritySection from './SecuritySection';

const Settings: FC = () => {
  const { user: currentUser, setUser } = useAppUser<HowlerUser>();
  const { editName, editPassword, editQuota, addApiKey, removeApiKey, addRole, removeRole, viewGroups } =
    useMyUserFunctions();

  const { get } = useMyLocalStorage();

  const isOAuth = useMemo(() => get<string>(StorageKey.APP_TOKEN)?.includes('.'), [get]);

  const currentUserWrapper =
    <T,>(fn: (user: HowlerUser, newValue: T) => Promise<HowlerUser>) =>
    async (value: T) => {
      setUser(await fn(currentUser, value));
    };

  return (
    <UserPageWrapper user={currentUser}>
      <ProfileSection
        user={currentUser}
        editName={!isOAuth ? currentUserWrapper(editName) : undefined}
        addRole={currentUser.is_admin && !isOAuth ? currentUserWrapper(addRole) : undefined}
        removeRole={currentUser.is_admin && !isOAuth ? currentUserWrapper(removeRole) : undefined}
        viewGroups={viewGroups}
      />
      <SecuritySection
        user={currentUser}
        editPassword={editPassword}
        addApiKey={addApiKey}
        removeApiKey={currentUserWrapper(removeApiKey)}
        editQuota={currentUser.is_admin ? currentUserWrapper(editQuota) : undefined}
      />
      <LocalSection />
      {currentUser.roles!.includes('admin') && <AdminSection />}
    </UserPageWrapper>
  );
};

export default Settings;
