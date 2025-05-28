import api, { type HowlerResponse } from 'api';
import type { PostLoginBody } from 'api/auth/login';
import { useAppUser } from 'commons/components/app/hooks';
import { ModalContext } from 'components/app/providers/ModalProvider';
import LoginErrorModal from 'components/elements/display/modals/LoginErrorModal';
import useMyApi from 'components/hooks/useMyApi';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { StorageKey } from 'utils/constants';
import { saveLoginCredential } from 'utils/localStorage';

const useLogin = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { dispatchApi } = useMyApi();
  const { setUser } = useAppUser<HowlerUser>();
  const { showErrorMessage } = useMySnackbar();
  const { t } = useTranslation();
  const { showModal } = useContext(ModalContext);
  const { get, remove } = useMyLocalStorage();

  // Get user information
  const getUser = useCallback(async () => {
    try {
      // We try and retrieve the user
      const user = await dispatchApi(api.user.whoami.get(), { showError: false, throwError: true });

      // If successful, continue
      if (user) {
        setUser({
          ...user,
          favourite_analytics: user.favourite_analytics ?? []
        });

        // Either navigate to the original URL, or just the home page
        if (get(StorageKey.NEXT_LOCATION)) {
          navigate(get<string>(StorageKey.NEXT_LOCATION) + (get<string>(StorageKey.NEXT_SEARCH) ?? ''));
          remove(StorageKey.NEXT_LOCATION);
          remove(StorageKey.NEXT_SEARCH);
        } else if (location.pathname === '/login') {
          navigate('/');
        }
        // If the user is null but there's no exception?
      } else {
        setUser(null);
        showErrorMessage(t('user.error.failed'));
      }
    } catch (e) {
      // There's some sort of error with the getting of the user - log them out or throw an error
      if (e instanceof Error) {
        if ((e.cause as HowlerResponse<any>)?.api_status_code === 403) {
          navigate('/logout');
        } else {
          showModal(<LoginErrorModal error={e} />, {
            disableClose: true
          });
        }
      }
    }
  }, [dispatchApi, setUser, get, location.pathname, navigate, remove, showErrorMessage, t, showModal]);

  // Generic login flow.
  const doLogin = useCallback(
    async (loginData: PostLoginBody) => {
      // Provide the login data to the API for the server to authenticate
      const userCredential = await dispatchApi(api.auth.login.post(loginData));

      if (!userCredential) {
        showErrorMessage(t('user.login.failed'));
      } else if (saveLoginCredential(userCredential)) {
        getUser();
      }
    },
    [dispatchApi, getUser, showErrorMessage, t]
  );

  // OAuth login flow.
  const doOAuth = useCallback(async () => {
    const userCredential = await dispatchApi(api.auth.login.get(searchParams));
    if (saveLoginCredential(userCredential)) {
      getUser();
    }
  }, [dispatchApi, searchParams, getUser]);

  // login service.
  return useMemo(
    () => ({
      doLogin,
      doOAuth,
      getUser
    }),
    [doLogin, doOAuth, getUser]
  );
};

export default useLogin;
