import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback } from 'react';

interface AvatarContextType {
  getAvatar: (id: string) => Promise<string>;
}

export const AvatarContext = createContext<AvatarContextType>(null);

/**
 * Because of the nature of requesting avatars, there's often LOTS of requests firing off in rapid succession,
 * too quickly for React to react (pardon the pun). To circumvent this, we just use a global object to remove race conditions.
 */
const promises: { [index: string]: Promise<string> } = {};

const AvatarProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const getAvatar = useCallback(
    (id: string) => {
      if (!id) {
        return Promise.resolve('');
      }

      if (promises[id]) {
        return promises[id];
      }

      try {
        promises[id] = dispatchApi(api.user.avatar.get(id), { logError: false, showError: false, throwError: false });

        return promises[id];
      } catch (e) {
        promises[id] = api.user.get(id).then(user => user.name);

        return promises[id];
      }
    },
    [dispatchApi]
  );

  return <AvatarContext.Provider value={{ getAvatar }}>{children}</AvatarContext.Provider>;
};

export default AvatarProvider;
