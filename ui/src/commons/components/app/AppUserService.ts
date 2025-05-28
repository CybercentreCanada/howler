// Describes a property of the AppUser
export type AppUserValidatedProp = {
  prop: string; // the key of the AppUser property.
  value: any; // the value it should compare with the AppUser's property.
};

// Specification interface describing an application user.
export type AppUser = {
  username?: string;
  email?: string;
  name?: string;
  avatar?: string;
  is_admin?: boolean;
};

export type AppUserService<T extends AppUser> = {
  user: T; // The application's current user.
  setUser: (user: T) => void; // Provide method to set the current user.
  isReady: () => boolean; // Indicate whether the current user is ready/available/authenticated.
  validateProps?: (props: AppUserValidatedProp[]) => boolean; // Decide whether leftnav menu items should be rendered for current user.
};
