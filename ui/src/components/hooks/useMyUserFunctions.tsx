import api from 'api';
import { useAppUser } from 'commons/components/app/hooks';
import ApiKeyDrawer from 'components/app/drawers/ApiKeyDrawer';
import ViewGroupsDrawer from 'components/app/drawers/ViewGroupsDrawer';
import { AppDrawerContext } from 'components/app/providers/AppDrawerProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import type { HowlerUser } from 'models/entities/HowlerUser';
import { useCallback, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import useMyApi from './useMyApi';
import useMySnackbar from './useMySnackbar';

const useMyUserFunctions = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { showSuccessMessage } = useMySnackbar();
  const { dispatchApi } = useMyApi();
  const { showModal } = useContext(ModalContext);
  const drawer = useContext(AppDrawerContext);
  const { user: currentUser, setUser } = useAppUser<HowlerUser>();

  return {
    editName: useCallback(
      async (user: HowlerUser, name: string) => {
        await dispatchApi(api.user.put(user.username, { name }), { throwError: true, showError: true });

        showSuccessMessage(t('api.user.name.updated'));

        return {
          ...user,
          name
        };
      },
      [dispatchApi, showSuccessMessage, t]
    ),

    editQuota: useCallback(
      async (user: HowlerUser, quota: string) => {
        // eslint-disable-next-line @typescript-eslint/naming-convention
        const api_quota = parseInt(quota);

        await dispatchApi(api.user.put(user.username, { api_quota }), { throwError: true });

        showSuccessMessage(t('api.user.quota.updated'));

        return {
          ...user,
          api_quota
        };
      },
      [dispatchApi, showSuccessMessage, t]
    ),

    editPassword: useCallback(
      async (new_pass: string) => {
        await dispatchApi(api.user.put(currentUser.username, { new_pass }), {
          throwError: true,
          showError: true
        });

        showSuccessMessage(t('password.success'));
        setTimeout(() => {
          navigate('/logout');
        }, 5000);
      },
      [currentUser.username, dispatchApi, navigate, showSuccessMessage, t]
    ),

    addRole: useCallback(
      async (user: HowlerUser, role: string) => {
        const newRoles = [...user.roles, role];

        await dispatchApi(api.user.put(user.username, { type: newRoles }), {
          throwError: true,
          showError: true
        });

        showSuccessMessage(t('api.user.role.updated'));

        return {
          ...user,
          roles: newRoles
        };
      },
      [dispatchApi, showSuccessMessage, t]
    ),

    addApiKey: useCallback(() => {
      drawer.open({
        titleKey: 'app.drawer.user.apikey.title',
        children: (
          <ApiKeyDrawer
            onCreated={(newKeyName, privs, expiryDate) => {
              setUser({
                ...currentUser,
                apikeys: [...currentUser.apikeys, [newKeyName, privs, expiryDate]]
              });

              showSuccessMessage(t('api.user.apikey.updated'));
            }}
          />
        )
      });
    }, [currentUser, drawer, setUser, showSuccessMessage, t]),

    removeRole: useCallback(
      async (user: HowlerUser, role: string) => {
        const newRoles = user.roles.filter(r => r !== role);

        await dispatchApi(api.user.put(user.username, { type: user.roles.filter(r => r !== role) }), {
          throwError: true,
          showError: true
        });

        showSuccessMessage(t('api.user.role.updated'));

        return {
          ...user,
          roles: newRoles
        };
      },
      [dispatchApi, showSuccessMessage, t]
    ),

    removeApiKey: useCallback(
      async (user: HowlerUser, apiKey: [string, string[]]) => {
        await new Promise<void>(res => {
          showModal(<ConfirmDeleteModal onConfirm={res} />);
        });

        await dispatchApi(api.auth.apikey.del(apiKey[0]), { throwError: true });

        showSuccessMessage(t('api.user.apikey.removed'));

        return {
          ...user,
          apikeys: user.apikeys.filter(([name, _]) => name !== apiKey[0])
        };
      },
      [dispatchApi, showModal, showSuccessMessage, t]
    ),

    viewGroups: useCallback(async () => {
      const groups = await dispatchApi(api.user.groups.get());

      drawer.open({
        titleKey: 'app.drawer.user.groups.title',
        children: <ViewGroupsDrawer groups={groups} />
      });
    }, [dispatchApi, drawer]),

    setDashboard: useCallback(
      async (dashboard: HowlerUser['dashboard']) => {
        await dispatchApi(api.user.put(currentUser.username, { dashboard }), {
          throwError: true,
          showError: true
        });
      },
      [currentUser.username, dispatchApi]
    )
  };
};

export default useMyUserFunctions;
