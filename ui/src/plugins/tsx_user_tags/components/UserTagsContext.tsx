import type { TagsDictionary, UserTags } from 'api/tags';
import { useFetchTagsDictionary } from 'plugins/tsx_hooks/user_tags/useFetchTagsDictionary';
import { useFetchUserTags } from 'plugins/tsx_hooks/user_tags/useFetchUserTags';
import { useMutateUserTags } from 'plugins/tsx_hooks/user_tags/useMutateUserTags';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';

export interface UserTagsContextValue {
  tagsDictionary: TagsDictionary;
  isLoadingTagsDictionary: boolean;
  userTags: UserTags;
  isLoadingUserTags: boolean;
  updateUserTags: (tags: UserTags) => void;
  isUpdatingUserTags: boolean;
  isUpdateSuccess: boolean;
  updateError: Error | null;
  resetUpdateStatus: () => void;
}

export const UserTagsContext = createContext<UserTagsContextValue | null>(null);

const DEFAULT_TAGS_DICTIONARY: TagsDictionary = {
  portfolio: [],
  products: [],
  primary_disciplines: []
};

const DEFAULT_USER_TAGS: UserTags = {
  portfolio: [],
  products: [],
  primary_disciplines: []
};

export const UserTagsProvider = ({ children }: { children: ReactNode }) => {
  const [isUpdateSuccess, setIsUpdateSuccess] = useState(false);
  const [updateError, setUpdateError] = useState<Error | null>(null);

  const { data: tagsDictionary, isLoading: isLoadingTagsDictionary } = useFetchTagsDictionary();
  const { data: userTags, isLoading: isLoadingUserTags, refetch: refetchUserTags } = useFetchUserTags();

  const { mutate: updateUserTags, isLoading: isUpdatingUserTags } = useMutateUserTags({
    onSuccess: () => {
      setIsUpdateSuccess(true);
      refetchUserTags();
    },
    onError: error => {
      setUpdateError(error);
    }
  });

  const resetUpdateStatus = useCallback(() => {
    setIsUpdateSuccess(false);
    setUpdateError(null);
  }, []);

  const handleUpdateUserTags = useCallback(
    (tags: UserTags) => {
      resetUpdateStatus();
      updateUserTags(tags);
    },
    [resetUpdateStatus, updateUserTags]
  );

  const contextValue = useMemo<UserTagsContextValue>(
    () => ({
      tagsDictionary: tagsDictionary || DEFAULT_TAGS_DICTIONARY,
      isLoadingTagsDictionary,
      userTags: userTags || DEFAULT_USER_TAGS,
      isLoadingUserTags,
      updateUserTags: handleUpdateUserTags,
      isUpdatingUserTags,
      isUpdateSuccess,
      updateError,
      resetUpdateStatus
    }),
    [
      tagsDictionary,
      isLoadingTagsDictionary,
      userTags,
      isLoadingUserTags,
      handleUpdateUserTags,
      isUpdatingUserTags,
      isUpdateSuccess,
      updateError,
      resetUpdateStatus
    ]
  );

  return <UserTagsContext.Provider value={contextValue}>{children}</UserTagsContext.Provider>;
};

export const useUserTagsContext = () => {
  const context = useContext(UserTagsContext);

  if (!context) {
    throw new Error('useUserTagsContext must be used within a UserTagsProvider');
  }

  return context;
};
