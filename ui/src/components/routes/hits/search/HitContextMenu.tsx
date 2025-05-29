import {
  Assignment,
  Check,
  Edit,
  HowToVote,
  KeyboardArrowRight,
  OpenInNew,
  QueryStats,
  SettingsSuggest
} from '@mui/icons-material';
import { Box, Divider, Fade, ListItemIcon, ListItemText, Menu, MenuItem, MenuList, Paper } from '@mui/material';
import api from 'api';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { VOTE_OPTIONS } from 'components/elements/hit/actions/SharedComponents';
import useHitActions from 'components/hooks/useHitActions';
import useMyApi from 'components/hooks/useMyApi';
import useMyActionFunctions from 'components/routes/action/useMyActionFunctions';
import type { Action } from 'models/entities/generated/Action';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { FC, MouseEventHandler, PropsWithChildren } from 'react';
import { useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useContextSelector } from 'use-context-selector';

// TODO: Eventually make this more generic

interface HitContextMenuProps {
  getSelectedId: (event: React.MouseEvent<HTMLDivElement, MouseEvent>) => string;
}

const HitContextMenu: FC<PropsWithChildren<HitContextMenuProps>> = ({ children, getSelectedId }) => {
  const { t } = useTranslation();
  const analyticContext = useContext(AnalyticContext);
  const { dispatchApi } = useMyApi();
  const { executeAction } = useMyActionFunctions();
  const { config } = useContext(ApiConfigContext);

  const [id, setId] = useState<string>(null);

  const hit = useContextSelector(HitContext, ctx => ctx.hits[id]);
  const selectedHits = useContextSelector(HitContext, ctx => ctx.selectedHits);

  const [analytic, setAnalytic] = useState<Analytic>(null);

  const [anchorEl, setAnchorEl] = useState<HTMLElement>();
  const [clickLocation, setClickLocation] = useState<[number, number]>([-1, -1]);
  const [actions, setActions] = useState<Action[]>([]);

  const [showAction, setShowAction] = useState(false);
  const [showAssess, setShowAssess] = useState(false);
  const [showVote, setShowVote] = useState(false);
  const [showManage, setShowManage] = useState(false);

  const { availableTransitions, canVote, canAssess, manage, assess, vote, selectedVote } = useHitActions(
    selectedHits.some(_hit => _hit.howler.id === hit?.howler.id) ? selectedHits : [hit]
  );

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
      setShowAction(false);
      setShowAssess(false);
      setShowVote(false);
      setShowManage(false);
      setAnalytic(null);
    }
  }, [anchorEl]);

  return (
    <Box id="contextMenu" onContextMenu={onContextMenu}>
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
        <MenuItem
          sx={{ position: 'relative' }}
          onMouseEnter={() => setShowAssess(true)}
          onMouseLeave={() => setShowAssess(false)}
          disabled={!canAssess}
        >
          <ListItemIcon>
            <Assignment />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('hit.details.actions.assess')}</ListItemText>
          {canAssess && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
          <Fade in={showAssess} unmountOnExit>
            <Paper
              sx={{ position: 'absolute', top: 0, left: '100%', maxHeight: '300px', overflow: 'auto' }}
              elevation={8}
            >
              <MenuList sx={{ p: 0, borderTopLeftRadius: 0 }} dense>
                {config.lookups['howler.assessment'].map(a => (
                  <MenuItem value={a} onClick={() => assess(a, analytic?.triage_settings.skip_rationale)} key={a}>
                    {a.replace(/^[a-z]/, val => val.toUpperCase())}
                  </MenuItem>
                ))}
              </MenuList>
            </Paper>
          </Fade>
        </MenuItem>
        <MenuItem
          sx={{ position: 'relative' }}
          onMouseEnter={() => setShowVote(true)}
          onMouseLeave={() => setShowVote(false)}
          disabled={!canVote}
        >
          <ListItemIcon>
            <HowToVote />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('hit.details.actions.vote')}</ListItemText>
          {canVote && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
          <Fade in={showVote} unmountOnExit>
            <Paper
              sx={{ position: 'absolute', top: 0, left: '100%', maxHeight: '300px', overflow: 'auto' }}
              elevation={8}
            >
              <MenuList sx={{ p: 0, borderTopLeftRadius: 0, minWidth: '150px' }} dense>
                {VOTE_OPTIONS.map(v => (
                  <MenuItem value={v.name} onClick={() => vote(v.name.toLowerCase())} key={v.name}>
                    <ListItemText>{v.name}</ListItemText>
                    {selectedVote === v.name.toLowerCase() && <Check fontSize="small" />}
                  </MenuItem>
                ))}
              </MenuList>
            </Paper>
          </Fade>
        </MenuItem>
        <MenuItem
          sx={{ position: 'relative' }}
          onMouseEnter={() => setShowManage(true)}
          onMouseLeave={() => setShowManage(false)}
        >
          <ListItemIcon>
            <Edit />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('hit.details.actions.transition')}</ListItemText>
          <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />
          <Fade in={showManage} unmountOnExit>
            <Paper
              sx={{ position: 'absolute', top: 0, left: '100%', maxHeight: '300px', overflow: 'auto' }}
              elevation={8}
            >
              <MenuList sx={{ p: 0, borderTopLeftRadius: 0, minWidth: '150px' }} dense>
                {availableTransitions.map(transition => (
                  <MenuItem
                    value={transition.name}
                    onClick={() => manage(transition.name.toLowerCase())}
                    key={transition.name}
                  >
                    <ListItemText>{t(`hit.details.actions.transition.${transition.name}`)}</ListItemText>
                    {selectedVote === transition.name.toLowerCase() && <Check fontSize="small" />}
                  </MenuItem>
                ))}
              </MenuList>
            </Paper>
          </Fade>
        </MenuItem>
        <MenuItem
          sx={{ position: 'relative' }}
          onMouseEnter={() => setShowAction(true)}
          onMouseLeave={() => setShowAction(false)}
          disabled={actions.length < 1}
        >
          <ListItemIcon>
            <SettingsSuggest />
          </ListItemIcon>
          <ListItemText sx={{ flex: 1 }}>{t('route.actions.change')}</ListItemText>
          {actions.length > 0 && <KeyboardArrowRight fontSize="small" sx={{ color: 'text.secondary', mr: -1 }} />}
          <Fade in={showAction} unmountOnExit>
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
    </Box>
  );
};

export default HitContextMenu;
