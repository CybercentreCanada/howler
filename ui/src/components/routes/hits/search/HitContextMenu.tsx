import {
  Assignment,
  Edit,
  HowToVote,
  KeyboardArrowRight,
  OpenInNew,
  QueryStats,
  RemoveCircleOutline,
  SettingsSuggest,
  Terminal
} from '@mui/icons-material';
import {
  Box,
  Divider,
  Fade,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  MenuList,
  Paper,
  type SxProps
} from '@mui/material';
import api from 'api';
import useMatchers from 'components/app/hooks/useMatchers';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { TOP_ROW, VOTE_OPTIONS, type ActionButton } from 'components/elements/hit/actions/SharedComponents';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import useMyActionFunctions from 'components/routes/action/useMyActionFunctions';
import { capitalize, get, groupBy, isEmpty } from 'lodash-es';
import type { Action } from 'models/entities/generated/Action';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Template } from 'models/entities/generated/Template';
import howlerPluginStore from 'plugins/store';
import type { FC, MouseEventHandler, PropsWithChildren } from 'react';
import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';
import { sanitizeLuceneQuery } from 'utils/stringUtils';

/**
 * Props for the HitContextMenu component
 */
interface HitContextMenuProps {
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
 * The margin at the bottom of the screen by which the context menu should be inverted.
 * That is, if right clicking within this many pixels of the bottom, render the context menu to the top right
 * of the pointer instead of the bottom right.
 */
const CONTEXTMENU_MARGIN = 350;

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
const HitContextMenu: FC<PropsWithChildren<HitContextMenuProps>> = ({ children, getSelectedId, Component = Box }) => {
  const { t } = useTranslation();
  const { dispatchApi } = useMyApi();
  const { executeAction } = useMyActionFunctions();
  const { config } = useContext(ApiConfigContext);
  const pluginStore = usePluginStore();
  const { getMatchingAnalytic, getMatchingTemplate } = useMatchers();
  const query = useContextSelector(ParameterContext, ctx => ctx.query);
  const setQuery = useContextSelector(ParameterContext, ctx => ctx.setQuery);

  const [id, setId] = useState<string>(null);

  const hit = useContextSelector(HitContext, ctx => ctx.hits[id]);
  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const [analytic, setAnalytic] = useState<Analytic>(null);
  const [template, setTemplate] = useState<Template>(null);

  const [anchorEl, setAnchorEl] = useState<HTMLElement>();
  const [transformProps, setTransformProps] = useState<SxProps>({});
  const [actions, setActions] = useState<Action[]>([]);

  const [show, setShow] = useState<{ [index: string]: EventTarget & HTMLElement }>({});

  const hits = useMemo(
    () => (selectedHits.some(_hit => _hit.howler.id === hit?.howler.id) ? selectedHits : [hit]),
    [hit, selectedHits]
  );

  const { availableTransitions, canVote, canAssess, assess, vote } = useHitActions(hits);

  /**
   * Handles right-click context menu events.
   * Opens the context menu at the click location and loads available actions.
   */
  const onContextMenu: MouseEventHandler<HTMLDivElement> = useCallback(
    async event => {
      if (anchorEl) {
        event.preventDefault();
        setAnchorEl(null);
        return;
      }
      event.preventDefault();

      const _id = getSelectedId(event);
      setId(_id);

      if (window.innerHeight - event.clientY < 300) {
        setTransformProps({
          position: 'fixed',
          bottom: `${window.innerHeight - event.clientY}px !important`,
          top: 'unset !important',
          left: `${event.clientX}px !important`
        });
      } else {
        setTransformProps({
          position: 'fixed',
          top: `${event.clientY}px !important`,
          left: `${event.clientX}px !important`
        });
      }

      setAnchorEl(event.target as HTMLElement);

      const _actions = (await dispatchApi(api.search.action.post({ query: 'action_id:*' }), { throwError: false }))
        ?.items;

      if (_actions) {
        setActions(_actions);
      }
    },
    [anchorEl, dispatchApi, getSelectedId]
  );

  const rowStatus = useMemo(
    () => ({
      assessment: canAssess,
      vote: canVote
    }),
    [canAssess, canVote]
  );

  const pluginActions = howlerPluginStore.plugins.flatMap(plugin =>
    pluginStore.executeFunction(`${plugin}.actions`, hits)
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

  /**
   * Calculates appropriate styles for submenu positioning.
   * Adjusts position based on available screen space to prevent overflow.
   */
  const calculateSubMenuStyles = useCallback((parent: HTMLElement) => {
    const baseStyles = { position: 'absolute', maxHeight: '300px', overflow: 'auto' };
    const defaultStyles = { ...baseStyles, top: 0, left: '100%' };

    if (!parent) {
      return defaultStyles;
    }

    const parentBounds = parent.getBoundingClientRect();

    if (window.innerHeight - parentBounds.y < CONTEXTMENU_MARGIN) {
      return { ...baseStyles, bottom: 0, left: '100%' };
    }

    return defaultStyles;
  }, []);

  // Load analytic and template data when a hit is selected
  useEffect(() => {
    if (!hit?.howler.analytic) {
      return;
    }

    getMatchingAnalytic(hit).then(setAnalytic);
    getMatchingTemplate(hit).then(setTemplate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit]);

  // Reset menu state when context menu is closed
  useEffect(() => {
    if (!anchorEl) {
      setShow({});
      setAnalytic(null);
    }
  }, [anchorEl]);

  return (
    <Component id="contextMenu" onContextMenu={onContextMenu}>
      {children}
      <Menu
        id="hit-menu"
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        slotProps={{
          paper: {
            sx: {
              ...transformProps,
              overflow: 'visible !important'
            }
          }
        }}
        MenuListProps={{ dense: true, sx: { minWidth: '250px' } }}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        onClick={() => setAnchorEl(null)}
      >
        <MenuItem component={Link} to={`/hits/${hit?.howler.id}`} disabled={!hit}>
          <ListItemIcon>
            <OpenInNew />
          </ListItemIcon>
          <ListItemText>{t('hit.panel.open')}</ListItemText>
        </MenuItem>
        <MenuItem component={Link} to={`/analytics/${analytic?.analytic_id}`} disabled={!analytic}>
          <ListItemIcon>
            <QueryStats />
          </ListItemIcon>
          <ListItemText>{t('hit.panel.analytic.open')}</ListItemText>
        </MenuItem>
        <Divider />
        {entries.map(([type, items]) => (
          <MenuItem
            key={type}
            id={`${type}-menu-item`}
            sx={{ position: 'relative' }}
            onMouseEnter={ev => setShow(_show => ({ ..._show, [type]: ev.target as EventTarget & HTMLLIElement }))}
            onMouseLeave={() => setShow(_show => ({ ..._show, [type]: null }))}
            disabled={rowStatus[type] === false}
          >
            <ListItemIcon>{ICON_MAP[type] ?? <Terminal />}</ListItemIcon>
            <ListItemText sx={{ flex: 1 }}>{t(`hit.details.actions.${type}`)}</ListItemText>
            {rowStatus[type] !== false && (
              <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />
            )}
            <Fade in={!!show[type]} unmountOnExit>
              <Paper id={`${type}-submenu`} sx={calculateSubMenuStyles(show[type])} elevation={8}>
                <MenuList sx={{ p: 0, borderTopLeftRadius: 0 }} dense role="group">
                  {items.map(a => (
                    <MenuItem value={a.name} onClick={a.actionFunction} key={a.name}>
                      {a.i18nKey ? t(a.i18nKey) : capitalize(a.name)}
                    </MenuItem>
                  ))}
                </MenuList>
              </Paper>
            </Fade>
          </MenuItem>
        ))}
        <MenuItem
          id="actions-menu-item"
          sx={{ position: 'relative' }}
          onMouseEnter={ev => setShow(_show => ({ ..._show, actions: ev.target as EventTarget & HTMLLIElement }))}
          onMouseLeave={() => setShow(_show => ({ ..._show, actions: null }))}
          disabled={actions.length < 1}
        >
          <ListItemIcon>
            <SettingsSuggest />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('route.actions.change')}</ListItemText>
          {actions.length > 0 && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
          <Fade in={!!show.actions} unmountOnExit>
            <Paper id="actions-submenu" sx={calculateSubMenuStyles(show.actions)} elevation={8}>
              <MenuList sx={{ p: 0 }} dense role="group">
                {actions.map(action => (
                  <MenuItem
                    key={action.action_id}
                    onClick={() => executeAction(action.action_id, `howler.id:${hit?.howler.id}`)}
                  >
                    <ListItemText>{action.name}</ListItemText>
                  </MenuItem>
                ))}
              </MenuList>
            </Paper>
          </Fade>
        </MenuItem>
        {!isEmpty(template?.keys ?? []) && (
          <>
            <Divider />
            <MenuItem
              id="excludes-menu-item"
              sx={{ position: 'relative' }}
              onMouseEnter={ev => setShow(_show => ({ ..._show, excludes: ev.target as EventTarget & HTMLLIElement }))}
              onMouseLeave={() => setShow(_show => ({ ..._show, excludes: null }))}
            >
              <ListItemIcon>
                <RemoveCircleOutline />
              </ListItemIcon>
              <ListItemText sx={{ flex: 1 }}>{t('hit.panel.exclude')}</ListItemText>
              <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />
              <Fade in={!!show.excludes} unmountOnExit>
                <Paper id="excludes-submenu" sx={calculateSubMenuStyles(show.excludes)} elevation={8}>
                  <MenuList sx={{ p: 0 }} dense role="group">
                    {template?.keys.map(key => {
                      // Build exclusion query based on current query and field value
                      let newQuery = '';
                      if (query !== 'howler.id:*') {
                        newQuery = `(${query}) AND `;
                      }

                      const value = get(hit, key);
                      if (!value) {
                        return null;
                      } else if (Array.isArray(value)) {
                        // Handle array values by excluding all items
                        const sanitizedValues = value
                          .map(toString)
                          .filter(val => !!val)
                          .map(val => `"${sanitizeLuceneQuery(val)}"`);

                        if (sanitizedValues.length < 1) {
                          return null;
                        }

                        newQuery += `-${key}:(${sanitizedValues.join(' OR ')})`;
                      } else {
                        // Handle single value
                        newQuery += `-${key}:"${value.toString()}"`;
                      }

                      return (
                        <MenuItem key={key} onClick={() => setQuery(newQuery)}>
                          <ListItemText>{key}</ListItemText>
                        </MenuItem>
                      );
                    })}
                  </MenuList>
                </Paper>
              </Fade>
            </MenuItem>
          </>
        )}
      </Menu>
    </Component>
  );
};

export default HitContextMenu;
