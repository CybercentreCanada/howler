import type { AppUserService, AppUserValidatedProp } from 'commons/components/app/AppUserService';
import { difference } from 'lodash-es';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useMemo, useState } from 'react';

// Application specific hook that will provide configuration to commons [useUser] hook.
const useMyUser = (): AppUserService<HowlerUser> => {
  const [user, setUser] = useState<HowlerUser>(null);

  const isReady = useCallback(() => !!user, [user]);

  const validateProps = useCallback(
    (props: AppUserValidatedProp[]) => {
      if (props === undefined) return true;

      return props.every((propDef: AppUserValidatedProp) => {
        if (Array.isArray(user[propDef.prop])) {
          return difference(propDef.value, user[propDef.prop]).length <= 0;
        } else {
          return user[propDef.prop] === propDef.value;
        }
      });
    },
    [user]
  );

  // We memoize the user config object to prevent unnecessary updates to user provider value.
  return useMemo(
    () => ({
      user,
      setUser,
      isReady,
      validateProps
    }),
    [user, setUser, isReady, validateProps]
  );
};

export default useMyUser;
