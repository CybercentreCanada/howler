import { UserListContext } from 'components/app/providers/UserListProvider';
import { useContext, useEffect } from 'react';

const useMyUserList = (ids: Set<string>) => {
  const { users, fetchUsers } = useContext(UserListContext);

  useEffect(() => {
    fetchUsers(ids);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids]);

  return users;
};

export default useMyUserList;
