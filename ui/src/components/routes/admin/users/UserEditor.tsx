import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import UserPageWrapper from 'components/elements/display/UserPageWrapper';
import useMyApi from 'components/hooks/useMyApi';
import useMyUserFunctions from 'components/hooks/useMyUserFunctions';
import ProfileSection from 'components/routes/settings/ProfileSection';
import SecuritySection from 'components/routes/settings/SecuritySection';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useEffect, useState, type FC } from 'react';
import { useParams } from 'react-router-dom';

const UserEditor: FC = () => {
  const { dispatchApi } = useMyApi();
  const { id } = useParams();
  const [user, setUser] = useState<HowlerUser>();
  const { user: currentUser } = useAppUser<HowlerUser>();
  const isAdmin = currentUser.is_admin;

  const { editName, editPassword, editQuota, addRole, removeRole, addApiKey, removeApiKey, viewGroups } =
    useMyUserFunctions();

  const userWrapper = useCallback(
    (fn: (user: HowlerUser, newValue: unknown) => Promise<HowlerUser>) => {
      return async (value: unknown) => setUser(await fn(user, value));
    },
    [user, setUser]
  );

  useEffect(() => {
    if (id && !user) {
      dispatchApi(api.user.get(id)).then(setUser);
    }
  }, [dispatchApi, id, user]);

  return (
    <UserPageWrapper user={user}>
      <ProfileSection
        user={user}
        editName={(isAdmin || currentUser.username === user?.username) && userWrapper(editName)}
        addRole={isAdmin && userWrapper(addRole)}
        removeRole={isAdmin && userWrapper(removeRole)}
        viewGroups={currentUser.username === user?.username && viewGroups}
      />
      <SecuritySection
        user={user}
        editPassword={currentUser.username === user?.username && editPassword}
        addApiKey={currentUser.username === user?.username && addApiKey}
        removeApiKey={(isAdmin || currentUser.username === user?.username) && userWrapper(removeApiKey)}
        editQuota={isAdmin && userWrapper(editQuota)}
      />
    </UserPageWrapper>
  );
};

export default UserEditor;
