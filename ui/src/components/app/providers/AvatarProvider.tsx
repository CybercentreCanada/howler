import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import type { FC, PropsWithChildren } from 'react';
import { createContext, useCallback } from 'react';
import { missingContext } from './contextUtils';

interface AvatarContextType {
  getAvatar: (id: string) => Promise<string>;
}

const DEFAULT_AVATAR_CONTEXT: AvatarContextType = {
  getAvatar: () => missingContext('AvatarContext')
};

export const AvatarContext = createContext<AvatarContextType>(DEFAULT_AVATAR_CONTEXT);

/**
 * Because of the nature of requesting avatars, there's often LOTS of requests firing off in rapid succession,
 * too quickly for React to react (pardon the pun). To circumvent this, we just use a global object to remove race conditions.
 */
const promises: { [index: string]: Promise<string> } = {};

const AvatarProvider: FC<PropsWithChildren> = ({ children }) => {
  const { dispatchApi } = useMyApi();

  const getAvatar = useCallback(
    (id: string): Promise<string> => {
      if (!id) {
        return Promise.resolve('');
      }

      const cachedAvatar = promises[id];
      if (cachedAvatar) {
        return cachedAvatar;
      }

      const fallback = async () => (await api.user.get(id))?.name ?? id;
      const avatarRequest = dispatchApi(api.user.avatar.get(id), {
        logError: false,
        showError: false,
        throwError: false
      })
        .then(avatar => avatar ?? fallback())
        .catch(() => fallback());
      promises[id] = avatarRequest;

      return avatarRequest;
    },
    [dispatchApi]
  );

  return <AvatarContext.Provider value={{ getAvatar }}>{children}</AvatarContext.Provider>;
};

export default AvatarProvider;
