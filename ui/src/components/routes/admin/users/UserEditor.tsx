import { useAppUser } from '@tui/core';
import api from 'api';
import UserPageWrapper from 'components/elements/display/UserPageWrapper';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserFunctions from 'components/hooks/useMyUserFunctions';
import ProfileSection from 'components/routes/settings/ProfileSection';
import SecuritySection from 'components/routes/settings/SecuritySection';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useEffect, useState, type FC } from 'react';
import { useParams } from 'react-router';

const UserEditor: FC = () => {
  const { dispatchApi } = useMyApi();
  const { id } = useParams();
  const [user, setUser] = useState<HowlerUser>();
  const { user: currentUser } = useAppUser<HowlerUser>();

  const isAdmin = currentUser.is_admin;
  const sameUser = currentUser.username === user?.username;

  const { editName, editPassword, editQuota, addRole, removeRole, addApiKey, removeApiKey, viewGroups } =
    useMyUserFunctions();

  const userWrapper = <T,>(fn: (user: HowlerUser, newValue: T) => Promise<HowlerUser>) => {
    return async (value: T) => {
      if (!user) {
        return;
      }

      setUser(await fn(user, value));
    };
  };

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
        editName={isAdmin || sameUser ? userWrapper(editName) : undefined}
        addRole={isAdmin ? userWrapper(addRole) : undefined}
        removeRole={isAdmin ? userWrapper(removeRole) : undefined}
        viewGroups={sameUser ? viewGroups : undefined}
      />
      <SecuritySection
        user={user}
        editPassword={sameUser ? editPassword : undefined}
        addApiKey={sameUser ? addApiKey : undefined}
        removeApiKey={isAdmin || sameUser ? userWrapper(removeApiKey) : undefined}
        editQuota={isAdmin ? userWrapper(editQuota) : undefined}
      />
    </UserPageWrapper>
  );
};

export default UserEditor;
