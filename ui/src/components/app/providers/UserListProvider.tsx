import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback, useEffect, useRef, useState } from 'react';

interface UserListContextType {
  users: { [id: string]: HowlerUser };
  searchUsers: (query: string) => void;
  fetchUsers: (ids: Set<string>) => void;
}

export const UserListContext = createContext<UserListContextType>(null);

const UserListProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const [users, setUsers] = useState<{ [id: string]: HowlerUser }>({});

  const usersRef = useRef(users);
  usersRef.current = users;

  const pendingIds = useRef<Set<string>>(new Set());
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
    (ids: Set<string>) => {
      const nextIds = new Set(ids);
      nextIds.delete('Unknown');
      nextIds.forEach(id => pendingIds.current.add(id));

      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }

      debounceTimer.current = setTimeout(async () => {
        const idsToGet = Array.from(pendingIds.current).filter(id => !Object.keys(usersRef.current).includes(id));
        pendingIds.current = new Set();
        debounceTimer.current = null;

        if (idsToGet.length <= 0) {
          return;
        }

        await searchUsers(`id:${idsToGet.join(' OR ')}`);
      }, 200);
    },
    [searchUsers]
  );

  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  return <UserListContext.Provider value={{ users, fetchUsers, searchUsers }}>{children}</UserListContext.Provider>;
};

export default UserListProvider;
