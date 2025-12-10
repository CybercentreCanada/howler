import api from 'api';
import type { HitTransitionBody } from 'api/hit';
import { useAppUser } from 'commons/components/app/hooks';
import AssignUserDrawer from 'components/app/drawers/AssignUserDrawer';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { AppDrawerContext } from 'components/app/providers/AppDrawerProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import RationaleModal from 'components/elements/display/modals/RationaleModal';
import type { ActionButton } from 'components/elements/hit/actions/SharedComponents';
import type { HowlerUser } from 'models/entities/HowlerUser';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import useMyApi from './useMyApi';
import useMySnackbar from './useMySnackbar';

export const MANAGE_OPTIONS: Partial<ActionButton>[] = [
  { type: 'action', name: 'release', key: 'R', i18nKey: `hit.details.actions.action.release` },
  { type: 'action', name: 'assign_to_other', key: 'T', i18nKey: `hit.details.actions.action.assign_to_other` },
  { type: 'action', name: 'start', key: 'Y', i18nKey: `hit.details.actions.action.start` },
  { type: 'action', name: 'pause', key: 'U', i18nKey: `hit.details.actions.action.pause` },
  { type: 'action', name: 'resume', key: 'I', i18nKey: `hit.details.actions.action.resume` },
  { type: 'action', name: 'assign_to_me', key: 'O', i18nKey: `hit.details.actions.action.assign_to_me` },
  { type: 'action', name: 're_evaluate', key: 'P', i18nKey: `hit.details.actions.action.re_evaluate` },
  { type: 'action', name: 'demote', key: '-', i18nKey: `hit.details.actions.action.demote` },
  { type: 'action', name: 'promote', key: '+', i18nKey: `hit.details.actions.action.promote` }
];

type TransitionStates = 'in-progress' | 'on-hold' | 'open' | 'resolved';

const useHitActions = (_hits: Hit | Hit[]) => {
  const { t } = useTranslation();
  const config = useContext(ApiConfigContext);
  const { user } = useAppUser<HowlerUser>();
  const drawer = useContext(AppDrawerContext);
  const { showModal } = useContext(ModalContext);
  const { showWarningMessage } = useMySnackbar();
  const { dispatchApi } = useMyApi();

  const updateHit = useContextSelector(HitContext, ctx => ctx.updateHit);

  const [loading, setLoading] = useState(false);

  const hits = useMemo(() => (Array.isArray(_hits) ? _hits : [_hits]).filter(_hit => !!_hit), [_hits]);

  const canVote = useMemo(
    () => hits.every(hit => hit?.howler.assignment !== user.username || hit?.howler.status === 'in-progress'),
    [hits, user.username]
  );
  const canAssess = useMemo(
    () =>
      hits.every(
        hit => !(['on-hold', 'resolved'].includes(hit?.howler.status) && hit?.howler.assignment === user.username)
      ),
    [hits, user.username]
  );

  const selectedVote = useMemo(() => {
    if (hits.length !== 1) {
      return '';
    }

    const hit = hits[0];

    return hit?.howler.votes.benign.includes(user.email)
      ? 'benign'
      : hit?.howler.votes.malicious.includes(user.email)
        ? 'malicious'
        : hit?.howler.votes.obscure.includes(user.email)
          ? 'obscure'
          : '';
  }, [hits, user.email]);

  const onAssign = useCallback(
    () =>
      new Promise<string>((res, rej) => {
        let done = false;

        drawer.open({
          titleKey: 'hit.details.actions.assign',
          children: (
            <AssignUserDrawer
              skipSubmit
              ids={hits.map(hit => hit.howler.id)}
              assignment={
                (hits.every(hit => hit.howler.assignment === hits[0].howler.assignment) &&
                  hits[0]?.howler.assessment) ||
                'unassigned'
              }
              onAssigned={h => {
                done = true;
                drawer.close();
                res(h);
              }}
            />
          ),
          onClosed: () => {
            if (!done) {
              rej('unassigned');
            }
          }
        });
      }),
    [drawer, hits]
  );

  const vote = useCallback(
    async (v: string) => {
      if (v !== selectedVote) {
        setLoading(true);

        try {
          await Promise.all(
            hits.map(async hit => {
              const _vote = () =>
                api.hit.transition.post(hit?.howler.id, { transition: 'vote', data: { vote: v, email: user.email } });

              const updatedHit: Hit = await dispatchApi(_vote(), {
                onConflict: async () => {
                  await api.hit.get(hit?.howler.id);

                  const newResult = await _vote();

                  updateHit(newResult);
                }
              });

              if (updatedHit) {
                updateHit(updatedHit);
              }
            })
          );
        } finally {
          setLoading(false);
        }
      }
    },
    [dispatchApi, hits, selectedVote, updateHit, user.email]
  );

  const assess = useCallback(
    async (assessment: string, skipRationale = false) => {
      const rationale = skipRationale
        ? t('rationale.default', { assessment })
        : await new Promise<string>(res => {
            showModal(
              <RationaleModal
                hits={hits}
                onSubmit={_rationale => {
                  res(_rationale);
                }}
              />
            );
          });

      await Promise.all(
        hits.map(async hit => {
          if (assessment !== hit?.howler.assessment) {
            setLoading(true);

            try {
              const update = () =>
                api.hit.transition.post(hit?.howler.id, { transition: 'assess', data: { assessment, rationale } });

              const updatedHit = await dispatchApi(update(), {
                onConflict: async () => {
                  const updatedData = await api.hit.get(hit?.howler.id);

                  if (!updatedData.howler.assessment) {
                    const result = await update();

                    updateHit(result);
                  } else {
                    updateHit(updatedData);
                    showWarningMessage(t('hit.actions.conflict.assess'));
                  }
                }
              });

              if (updatedHit) {
                updateHit(updatedHit);
              }
            } finally {
              setLoading(false);
            }
          }
        })
      );
    },
    [dispatchApi, hits, showModal, showWarningMessage, t, updateHit]
  );

  const manage = useCallback(
    async (transition: string) => {
      setLoading(true);
      try {
        const data: HitTransitionBody['data'] = {};

        if (transition === 'assign_to_other') {
          data.assignee = await onAssign();
        }

        await Promise.all(
          hits.map(async hit => {
            const update = () => api.hit.transition.post(hit?.howler.id, { transition, data });
            const updatedHit = await dispatchApi(update(), {
              onConflict: async () => {
                const updatedData = await api.hit.get(hit?.howler.id);
                updateHit(updatedData);
                showWarningMessage(t('hit.actions.conflict.manage'));
              }
            });

            if (updatedHit && updateHit) {
              updateHit(updatedHit);
            }
          })
        );
      } catch (e) {
        if (e !== 'unassigned') {
          throw e;
        }
      } finally {
        setLoading(false);
      }
    },
    [dispatchApi, hits, onAssign, showWarningMessage, t, updateHit]
  );

  const availableTransitions = useMemo(
    () =>
      MANAGE_OPTIONS.filter(option => {
        const name = option.name.toLowerCase();

        // Is this option one that is valid for the current state?
        return hits.every(
          hit =>
            config.config.lookups?.transitions[hit?.howler.status as TransitionStates]?.includes(name) &&
            // If we are assigning or voting, the hit can't be assigned to the current user
            ((name !== 'assign_to_me' && name !== 'vote') || hit?.howler.assignment !== user.username) &&
            // If we are running any of these actions, the current user must be assigned the hit
            ((name !== 'release' && name !== 'start' && name !== 'resume' && name !== 'pause') ||
              hit?.howler.assignment === user.username) &&
            // If we're promoting, it has to be a hit
            (name !== 'promote' || hit?.howler.escalation === 'hit') &&
            // If we're demoting, it has to be an alert
            (name !== 'demote' || hit?.howler.escalation === 'alert')
        );
      }).map<ActionButton>(
        option =>
          ({
            ...option,
            actionFunction: () => {
              if (!loading) {
                manage(option.name.toLowerCase());
              }
            }
          }) as ActionButton
      ),
    [config.config.lookups?.transitions, hits, loading, manage, user.username]
  );

  return {
    availableTransitions,
    canVote,
    canAssess,
    loading,
    manage,
    assess,
    vote,
    selectedVote
  };
};

export default useHitActions;
