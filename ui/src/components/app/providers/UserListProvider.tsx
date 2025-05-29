import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useState } from 'react';

interface UserListContextType {
  users: { [id: string]: HowlerUser };
  searchUsers: (query: string) => void;
  fetchUsers: (ids: Set<string>) => void;
}

export const UserListContext = createContext<UserListContextType>(null);

const UserListProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const [users, setUsers] = useState<{ [id: string]: HowlerUser }>({});

  const searchUsers = useCallback(
    async (query: string) => {
      const newUsers = (
        await dispatchApi(api.search.user.post({ query, rows: 1000 }), {
          throwError: false,
          logError: false,
          showError: false
        })
      )?.items?.reduce((dict, user) => ({ ...dict, [user.username]: user }), {});

      setUsers(_users => ({
        ..._users,
        ...newUsers
      }));
    },
    [dispatchApi]
  );

  const fetchUsers = useCallback(
    async (ids: Set<string>) => {
      ids.delete('Unknown');

      const idsToGet = Array.from(ids.values()).filter(id => !Object.keys(users).includes(id));

      if (idsToGet.length <= 0) {
        return;
      }

      await searchUsers(`id:${[...idsToGet].join(' OR ')}`);
    },
    [searchUsers, users]
  );

  return <UserListContext.Provider value={{ users, fetchUsers, searchUsers }}>{children}</UserListContext.Provider>;
};

export default UserListProvider;
