import { AppUserContext } from 'commons/components/app/AppContexts';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import { type ReactNode } from 'react';

type AppUserProviderProps<U extends AppUser> = {
  service: AppUserService<U>;
  children: ReactNode;
};

const AppUserServiceImpl: AppUserService<AppUser> = {
  user: null,
  setUser: () => undefined,
  isReady: () => false,
  validateProps: () => true
};

export default function AppUserProvider<U extends AppUser>({
  service = AppUserServiceImpl as unknown as AppUserService<U>,
  children
}: AppUserProviderProps<U>) {
  return <AppUserContext.Provider value={{ ...AppUserServiceImpl, ...service } as unknown as AppUserService<AppUser>}>{children}</AppUserContext.Provider>;
}
