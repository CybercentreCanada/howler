import { useAppUser } from '@tui/core';
import api from 'api';
import UserPageWrapper from 'components/elements/display/UserPageWrapper';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserFunctions from 'components/hooks/useMyUserFunctions';
import ProfileSection from 'components/routes/settings/ProfileSection';
import SecuritySection from 'components/routes/settings/SecuritySection';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useParams } from 'react-router';

const UserEditor: FC = () => {
  const { dispatchApi } = useMyApi();
  const { id } = useParams();
  const [user, setUser] = useState<HowlerUser>();
  const { user: currentUser } = useAppUser<HowlerUser>();
  const isAdmin = currentUser.is_admin;

  const { editName, editPassword, editQuota, addRole, removeRole, addApiKey, removeApiKey, viewGroups } =
    useMyUserFunctions();

  const userWrapper = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (fn: (user: HowlerUser, newValue: any) => Promise<HowlerUser>) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return async (value: any) => {
        if (!user) {
          return;
        }

        setUser(await fn(user, value));
      };
    },
    [user, setUser]
  );

  useEffect(() => {
    if (id && !user) {
      void dispatchApi(api.user.get(id)).then(result => {
        if (result) {
          setUser(result);
        }
      });
    }
  }, [dispatchApi, id, user]);

  if (!user) {
    return null;
  }

  return (
    <UserPageWrapper user={user}>
      <ProfileSection
        user={user}
        editName={isAdmin || currentUser.username === user?.username ? userWrapper(editName) : undefined}
        addRole={isAdmin ? userWrapper(addRole) : undefined}
        removeRole={isAdmin ? userWrapper(removeRole) : undefined}
        viewGroups={currentUser.username === user?.username ? viewGroups : undefined}
      />
      <SecuritySection
        user={user}
        editPassword={currentUser.username === user?.username ? editPassword : undefined}
        addApiKey={currentUser.username === user?.username ? addApiKey : undefined}
        removeApiKey={isAdmin || currentUser.username === user?.username ? userWrapper(removeApiKey) : undefined}
        editQuota={isAdmin ? userWrapper(editQuota) : undefined}
      />
    </UserPageWrapper>
  );
};

export default UserEditor;
