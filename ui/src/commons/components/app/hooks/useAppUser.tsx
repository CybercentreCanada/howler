import { AppUserContext } from 'commons/components/app/AppContexts';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import { useContext } from 'react';

export function useAppUser<U extends AppUser>(): AppUserService<U> {
  return useContext(AppUserContext) as AppUserService<U>;
}
