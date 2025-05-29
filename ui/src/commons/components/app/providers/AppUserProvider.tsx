import { AppUserContext } from 'commons/components/app/AppContexts';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import { type ReactNode } from 'react';

type AppUserProviderProps<U extends AppUser> = {
  service: AppUserService<U>;
  children: ReactNode;
};

const AppUserServiceImpl = {
  user: null,
  setUser: () => null,
  isReady: () => false,
  validateProps: () => true
};

export default function AppUserProvider<U extends AppUser>({
  service = AppUserServiceImpl,
  children
}: AppUserProviderProps<U>) {
  return <AppUserContext.Provider value={{ ...AppUserServiceImpl, ...service }}>{children}</AppUserContext.Provider>;
}
