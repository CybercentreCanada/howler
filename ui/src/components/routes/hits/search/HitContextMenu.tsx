import {
  Assignment,
  Edit,
  HowToVote,
  KeyboardArrowRight,
  OpenInNew,
  QueryStats,
  SettingsSuggest,
  Terminal
} from '@mui/icons-material';
import { Box, Divider, Fade, ListItemIcon, ListItemText, Menu, MenuItem, MenuList, Paper } from '@mui/material';
import api from 'api';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { TOP_ROW, VOTE_OPTIONS, type ActionButton } from 'components/elements/hit/actions/SharedComponents';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import useMyActionFunctions from 'components/routes/action/useMyActionFunctions';
import { capitalize, groupBy } from 'lodash-es';
import type { Action } from 'models/entities/generated/Action';
import type { Analytic } from 'models/entities/generated/Analytic';
import howlerPluginStore from 'plugins/store';
import type { FC, MouseEventHandler, PropsWithChildren } from 'react';
import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { usePluginStore } from 'react-pluggable';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

// TODO: Eventually make this more generic

interface HitContextMenuProps {
  getSelectedId: (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => string;
  Component?: React.ElementType;
}

const ORDER = ['assessment', 'vote', 'action'];
const ICON_MAP = {
  assessment: <Assignment />,
  vote: <HowToVote />,
  action: <Edit />
};

const HitContextMenu: FC<PropsWithChildren<HitContextMenuProps>> = ({ children, getSelectedId, Component = Box }) => {
  const { t } = useTranslation();
  const analyticContext = useContext(AnalyticContext);
  const { dispatchApi } = useMyApi();
  const { executeAction } = useMyActionFunctions();
  const { config } = useContext(ApiConfigContext);
  const pluginStore = usePluginStore();

  const [id, setId] = useState<string>(null);

  const hit = useContextSelector(HitContext, ctx => ctx.hits[id]);
  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const [analytic, setAnalytic] = useState<Analytic>(null);

  const [anchorEl, setAnchorEl] = useState<HTMLElement>();
  const [clickLocation, setClickLocation] = useState<[number, number]>([-1, -1]);
  const [actions, setActions] = useState<Action[]>([]);

  const [show, setShow] = useState<{ [index: string]: boolean }>({});

  const hits = useMemo(
    () => (selectedHits.some(_hit => _hit.howler.id === hit?.howler.id) ? selectedHits : [hit]),
    [hit, selectedHits]
  );

  const { availableTransitions, canVote, canAssess, assess, vote } = useHitActions(hits);

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

      const clientRect = (event.target as HTMLElement).getBoundingClientRect();
      setClickLocation([event.clientX - clientRect.x, event.clientY - clientRect.y]);

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

  useEffect(() => {
    if (!hit) {
      return;
    }

    (async () => {
      setAnalytic(await analyticContext.getAnalyticFromName(hit.howler.analytic));
    })();
  }, [analyticContext, hit]);

  useEffect(() => {
    if (!anchorEl) {
      setClickLocation([-1, -1]);
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
              transform: `translate(${clickLocation[0]}px, ${clickLocation[1]}px) !important`,
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
            sx={{ position: 'relative' }}
            onMouseEnter={() => setShow(_show => ({ ..._show, [type]: true }))}
            onMouseLeave={() => setShow(_show => ({ ..._show, [type]: false }))}
            disabled={rowStatus[type] === false}
          >
            <ListItemIcon>{ICON_MAP[type] ?? <Terminal />}</ListItemIcon>
            <ListItemText sx={{ flex: 1 }}>{t(`hit.details.actions.${type}`)}</ListItemText>
            {rowStatus[type] !== false && (
              <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />
            )}
            <Fade in={show[type]} unmountOnExit>
              <Paper
                sx={{ position: 'absolute', top: 0, left: '100%', maxHeight: '300px', overflow: 'auto' }}
                elevation={8}
              >
                <MenuList sx={{ p: 0, borderTopLeftRadius: 0 }} dense>
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
          sx={{ position: 'relative' }}
          onMouseEnter={() => setShow(_show => ({ ..._show, actions: true }))}
          onMouseLeave={() => setShow(_show => ({ ..._show, actions: false }))}
          disabled={actions.length < 1}
        >
          <ListItemIcon>
            <SettingsSuggest />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('route.actions.change')}</ListItemText>
          {actions.length > 0 && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
          <Fade in={show.actions} unmountOnExit>
            <Paper
              sx={{ position: 'absolute', top: 0, left: '100%', maxHeight: '300px', overflow: 'auto' }}
              elevation={8}
            >
              <MenuList sx={{ p: 0 }} dense>
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
      </Menu>
    </Component>
  );
};

export default HitContextMenu;
