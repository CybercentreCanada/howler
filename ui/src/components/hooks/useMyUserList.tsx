import { UserListContext } from 'components/app/providers/UserListProvider';
import { useContext, useEffect } from 'react';

const useMyUserList = (ids: Set<string>) => {
  const userListContext = useContext(UserListContext);
  const users = userListContext?.users || {};
  const fetchUsers = userListContext?.fetchUsers;

  useEffect(() => {
    if (!fetchUsers || !ids || ids.size <= 0) {
      return;
    }

    // Clone ids so downstream logic can mutate without affecting caller-owned Set.
    fetchUsers(new Set(ids));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchUsers, ids]);

  return users;
};

export default useMyUserList;
