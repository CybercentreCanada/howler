import { AppUserContext } from 'commons/components/app/AppContexts';
import type { AppUser, AppUserService } from 'commons/components/app/AppUserService';
import { type ReactNode } from 'react';

type AppUserProviderProps<U extends AppUser> = {
  service?: AppUserService<U>;
  children: ReactNode;
};

const createDefaultAppUserService = <U extends AppUser>(): AppUserService<U> => ({
  user: {} as U,
  setUser: () => undefined,
  isReady: () => false,
  validateProps: () => true
});

export default function AppUserProvider<U extends AppUser>({ service, children }: AppUserProviderProps<U>) {
  const appUserService = service ?? createDefaultAppUserService<U>();

  // AppUserContext is shared by applications with different user subtypes.
  const contextValue = appUserService as unknown as AppUserService<AppUser>;

  return <AppUserContext.Provider value={contextValue}>{children}</AppUserContext.Provider>;
}
