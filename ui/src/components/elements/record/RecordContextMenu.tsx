import {
  AddCircleOutline,
  Assignment,
  CreateNewFolder,
  Edit,
  HowToVote,
  OpenInNew,
  QueryStats,
  RemoveCircleOutline,
  SettingsSuggest,
  Terminal
} from '@mui/icons-material';
import api from 'api';
import useMatchers from 'components/app/hooks/useMatchers';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { ModalContext } from 'components/app/providers/ModalProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { RecordContext } from 'components/app/providers/RecordProvider';
import ContextMenu, { type ContextMenuEntry } from 'components/elements/ContextMenu';
import { TOP_ROW, VOTE_OPTIONS, type ActionButton } from 'components/elements/hit/actions/SharedComponents';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import useMyActionFunctions from 'components/routes/action/useMyActionFunctions';
import AddToCaseModal from 'components/routes/cases/modals/AddToCaseModal';
import { capitalize, get, groupBy, isEmpty, toString } from 'lodash-es';
import type { Action } from 'models/entities/generated/Action';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { Template } from 'models/entities/generated/Template';
import howlerPluginStore from 'plugins/store';
import type { FC, PropsWithChildren } from 'react';
import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { useContextSelector } from 'use-context-selector';
import { DEFAULT_QUERY } from 'utils/constants';
import { sanitizeLuceneQuery } from 'utils/stringUtils';
import { isHit } from 'utils/typeUtils';

/**
 * Props for the HitContextMenu component
 */
interface RecordContextMenuProps {
  /**
   * Function to extract the hit ID from a mouse event
   */
  getSelectedId: (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => string;

  /**
   * Optional component to wrap the children, defaults to Box
   */
  Component?: React.ElementType;
}

/**
 * Order in which action types should be displayed in the context menu
 */
const ORDER = ['assessment', 'vote', 'action'];

/**
 * Icon mapping for different action types
 */
const ICON_MAP = {
  assessment: <Assignment />,
  vote: <HowToVote />,
  action: <Edit />
};

/**
 * Context menu component for hit operations.
 * Provides quick access to common hit actions including assessment, voting,
 * transitions, and exclusion filters based on template fields.
 */
const RecordContextMenu: FC<PropsWithChildren<RecordContextMenuProps>> = ({ children, getSelectedId, Component }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { executeAction } = useMyActionFunctions();
  const { config } = useContext(ApiConfigContext);
  const { showModal } = useContext(ModalContext);
  const pluginStore = usePluginStore();
  const { getMatchingAnalytic, getMatchingTemplate } = useMatchers();
  const query = useContextSelector(ParameterContext, ctx => ctx?.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx?.setQuery);

  const [id, setId] = useState<string>(null);

  const record = useContextSelector(RecordContext, ctx => ctx.records[id] as Hit);
  const selectedRecords = useContextSelector(RecordContext, ctx => ctx.selectedRecords);

  const [analytic, setAnalytic] = useState<Analytic>(null);
  const [template, setTemplate] = useState<Template>(null);

  const [actions, setActions] = useState<Action[]>([]);

  const records = useMemo(
    () =>
      selectedRecords.some(_record => _record.howler.id === record?.howler.id)
        ? selectedRecords
        : record
          ? [record]
          : [],
    [record, selectedRecords]
  );

  const hits = useMemo(() => records.filter(isHit), [records]);

  const { availableTransitions, canVote, canAssess, assess, vote } = useHitActions(hits);

  /**
   * Called by ContextMenu after the menu is positioned and opened.
   * Identifies the clicked record and fetches available actions.
   */
  const onOpen = useCallback(
    async (event: React.MouseEvent<HTMLElement, MouseEvent>) => {
      const _id = getSelectedId(event as React.MouseEvent<HTMLDivElement, MouseEvent>);
      setId(_id);

      const _actions = (await dispatchApi(api.search.action.post({ query: 'action_id:*' }), { throwError: false }))
        ?.items;

      if (_actions) {
        setActions(_actions);
      }
    },
    [dispatchApi, getSelectedId]
  );

  const rowStatus = useMemo(
    () => ({
      assessment: canAssess,
      vote: canVote
    }),
    [canAssess, canVote]
  );

  const pluginActions = howlerPluginStore.plugins.flatMap(plugin =>
    pluginStore.executeFunction(`${plugin}.actions`, records)
  );

  /**
   * Generates grouped action entries for the context menu.
   * Combines transitions, plugin actions, votes, and assessments based on permissions.
   */
  const entries = useMemo<[string, ActionButton[]][]>(() => {
    let _actions: ActionButton[] = [...availableTransitions, ...pluginActions];

    if (canVote) {
      _actions = [
        ..._actions,
        ...VOTE_OPTIONS.map(
          option => ({ ...option, actionFunction: () => vote(option.name.toLowerCase()) }) as ActionButton
        )
      ];
    }

    if (config.lookups?.['howler.assessment'] && canAssess) {
      _actions = [
        ..._actions,
        ...config.lookups['howler.assessment']
          .filter(_assessment =>
            analytic?.triage_settings?.valid_assessments
              ? analytic.triage_settings?.valid_assessments.includes(_assessment)
              : true
          )
          .sort((a, b) => +TOP_ROW.includes(b) - +TOP_ROW.includes(a))
          .map<ActionButton>(assessment => ({
            type: 'assessment',
            name: assessment,
            actionFunction: async () => {
              await assess(assessment, analytic?.triage_settings?.skip_rationale);
            }
          }))
      ];
    }

    return Object.entries(groupBy(_actions, 'type')).sort(([a], [b]) => ORDER.indexOf(a) - ORDER.indexOf(b));
  }, [analytic, assess, availableTransitions, canAssess, canVote, config.lookups, vote, pluginActions]);

  // Load analytic and template data when a hit is selected
  useEffect(() => {
    if (!record?.howler.analytic) {
      return;
    }

    getMatchingAnalytic(record).then(setAnalytic);
    getMatchingTemplate(record).then(setTemplate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record]);

  /**
   * Builds the declarative items structure for the ContextMenu component.
   */
  const items = useMemo<ContextMenuEntry[]>(() => {
    const result: ContextMenuEntry[] = [
      {
        kind: 'item',
        id: 'open-record',
        icon: <OpenInNew />,
        label: t(`${record?.__index ?? 'hit'}.open`),
        disabled: !record,
        to: `/${record?.__index}s/${record?.howler.id}`
      }
    ];

    if (isHit(record)) {
      result.push({
        kind: 'item',
        id: 'open-analytic',
        icon: <QueryStats />,
        label: t('analytic.open'),
        disabled: !analytic,
        to: `/analytics/${analytic?.analytic_id}`
      });

      result.push({ kind: 'divider', id: 'actions-divider' });

      for (const [type, typeItems] of entries) {
        result.push({
          kind: 'submenu',
          id: type,
          icon: ICON_MAP[type] ?? <Terminal />,
          label: t(`hit.details.actions.${type}`),
          disabled: rowStatus[type] === false,
          items: typeItems.map(a => ({
            key: a.name,
            label: a.i18nKey ? t(a.i18nKey) : capitalize(a.name),
            onClick: a.actionFunction
          }))
        });
      }

      result.push({
        kind: 'submenu',
        id: 'actions',
        icon: <SettingsSuggest />,
        label: t('route.actions.change'),
        disabled: actions.length < 1,
        items: actions.map(action => ({
          key: action.action_id,
          label: action.name,
          onClick: () => executeAction(action.action_id, `howler.id:${record?.howler.id}`)
        }))
      });

      if (!isEmpty(template?.keys ?? []) && setQuery) {
        result.push({ kind: 'divider', id: 'filter-divider' });

        result.push({
          kind: 'submenu',
          id: 'excludes',
          icon: <RemoveCircleOutline />,
          label: t('hit.panel.exclude'),
          items: (template?.keys ?? []).flatMap(key => {
            let newQuery = '';
            if (query !== DEFAULT_QUERY) {
              newQuery = `(${query}) AND `;
            }
            const value = get(record, key);
            if (!value) {
              return [];
            } else if (Array.isArray(value)) {
              const sanitizedValues = value
                .map(toString)
                .filter(val => !!val)
                .map(val => `"${sanitizeLuceneQuery(val)}"`);
              if (sanitizedValues.length < 1) {
                return [];
              }
              newQuery += `-${key}:(${sanitizedValues.join(' OR ')})`;
            } else {
              newQuery += `-${key}:"${sanitizeLuceneQuery(value.toString())}"`;
            }
            return [{ key, label: key, onClick: () => setQuery(newQuery) }];
          })
        });

        result.push({
          kind: 'submenu',
          id: 'includes',
          icon: <AddCircleOutline />,
          label: t('hit.panel.include'),
          items: (template?.keys ?? []).flatMap(key => {
            let newQuery = `(${query}) AND `;
            const value = get(record, key);
            if (!value) {
              return [];
            } else if (Array.isArray(value)) {
              const sanitizedValues = value
                .map(toString)
                .filter(val => !!val)
                .map(val => `"${sanitizeLuceneQuery(val)}"`);
              if (sanitizedValues.length < 1) {
                return [];
              }
              newQuery += `${key}:(${sanitizedValues.join(' OR ')})`;
            } else {
              newQuery += `${key}:"${sanitizeLuceneQuery(value.toString())}"`;
            }
            return [{ key, label: key, onClick: () => setQuery(newQuery) }];
          })
        });
      }
    }

    result.push({ kind: 'divider', id: 'add-to-case-divider' });
    result.push({
      kind: 'item',
      id: 'add-to-case',
      icon: <CreateNewFolder />,
      label: t('modal.cases.add_to_case'),
      disabled: !record,
      onClick: () => showModal(<AddToCaseModal records={records} />)
    });

    return result;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record, analytic, template, entries, rowStatus, actions, query, t, setQuery, executeAction, showModal, records]);

  return (
    <ContextMenu id="contextMenu" Component={Component} onOpen={onOpen} onClose={() => setAnalytic(null)} items={items}>
      {children}
    </ContextMenu>
  );
};

export default RecordContextMenu;
