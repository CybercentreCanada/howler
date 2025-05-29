import { MoreHoriz } from '@mui/icons-material';
import {
  Box,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  FormLabel,
  IconButton,
  Menu,
  Radio,
  RadioGroup,
  Stack,
  Switch,
  useMediaQuery
} from '@mui/material';
import { AnalyticContext } from 'components/app/providers/AnalyticProvider';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { HitContext } from 'components/app/providers/HitProvider';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import { ParameterContext } from 'components/app/providers/ParameterProvider';
import { ViewContext } from 'components/app/providers/ViewProvider';
import useHitActions from 'components/hooks/useHitActions';
import { useMyLocalStorageProvider } from 'components/hooks/useMyLocalStorage';
import json2mq from 'json2mq';
import type { Analytic } from 'models/entities/generated/Analytic';
import type { Hit } from 'models/entities/generated/Hit';
import type { FC } from 'react';
import { memo, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { isMobile } from 'react-device-detect';
import { Trans } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import Throttler from 'utils/Throttler';
import { StorageKey } from 'utils/constants';
import { HitShortcuts } from './HitShortcuts';
import ButtonActions from './actions/ButtonActions';
import DropdownActions from './actions/DropdownActions';
import type { Keybinds } from './actions/SharedComponents';
import { ASSESSMENT_KEYBINDS, TOP_ROW, VOTE_OPTIONS } from './actions/SharedComponents';

const THROTTLER = new Throttler(250);
const HitActions: FC<{
  hit: Hit;
  orientation?: 'horizontal' | 'vertical';
}> = ({ hit, orientation = 'horizontal' }) => {
  const config = useContext(ApiConfigContext);
  const { values, set } = useMyLocalStorageProvider();

  const { getAnalyticFromName } = useContext(AnalyticContext);

  const getCurrentView = useContextSelector(ViewContext, ctx => ctx.getCurrentView);

  const selected = useContextSelector(ParameterContext, ctx => ctx?.selected);
  const setSelected = useContextSelector(ParameterContext, ctx => ctx?.setSelected);
  const clearSelectedHits = useContextSelector(HitContext, ctx => ctx.clearSelectedHits);
  const nextHit = useContextSelector(HitSearchContext, ctx => {
    if (!ctx?.response || !selected) {
      return null;
    }

    return ctx.response.items[(ctx.response.items.findIndex(_hit => _hit.howler.id === selected) ?? -1) + 1] ?? null;
  });

  const { availableTransitions, canVote, canAssess, loading, manage, assess, vote, selectedVote } = useHitActions([
    hit
  ]);

  const [openSetting, setOpenSetting] = useState<null | HTMLElement>(null);
  const [analytic, setAnalytic] = useState<Analytic>(null);

  const shortcuts = useMemo(
    () =>
      isMobile
        ? HitShortcuts.NO_SHORTCUTS
        : ((values[StorageKey.HIT_SHORTCUTS] as HitShortcuts) ?? HitShortcuts.SHORTCUTS_HINT),
    [values]
  );

  const forceDropdown = useMemo(() => (values[StorageKey.FORCE_DROPDOWN] as boolean) ?? false, [values]);

  const customActions = useMemo<Keybinds>(
    () => ({
      ...(canVote &&
        VOTE_OPTIONS.reduce(
          (obj, option) => ({ ...obj, [option.key]: () => vote(option.name.toLowerCase()) }),
          {} as Keybinds
        )),
      ...(canAssess &&
        config.config.lookups?.['howler.assessment']
          .filter(_assessment =>
            analytic?.triage_settings?.valid_assessments
              ? analytic.triage_settings?.valid_assessments.includes(_assessment)
              : true
          )
          ?.sort((a, b) => +TOP_ROW.includes(b) - +TOP_ROW.includes(a))
          .reduce(
            (obj, assessment, index) => ({
              ...obj,
              [ASSESSMENT_KEYBINDS[index]]: async () => {
                if (!loading) {
                  await assess(assessment, analytic?.triage_settings?.skip_rationale);

                  if (getCurrentView()?.settings?.advance_on_triage && nextHit) {
                    clearSelectedHits(nextHit.howler.id);
                    setSelected?.(nextHit.howler.id);
                  }
                }
              }
            }),
            {} as Keybinds
          )),
      ...availableTransitions.reduce((obj, option) => {
        if (
          config.config.lookups.transitions[
            hit?.howler.status as 'in-progress' | 'on-hold' | 'open' | 'resolved'
          ].includes(option.name.toLowerCase())
        ) {
          obj[option.key] = () => {
            if (!loading) {
              manage(option.name.toLowerCase());
            }
          };
        }
        return obj;
      }, {} as Keybinds)
    }),
    [
      analytic?.triage_settings,
      assess,
      availableTransitions,
      canAssess,
      canVote,
      clearSelectedHits,
      config.config.lookups,
      getCurrentView,
      hit?.howler.status,
      loading,
      manage,
      nextHit,
      setSelected,
      vote
    ]
  );

  const keyboardDownHandler = useCallback(
    (event: KeyboardEvent) => {
      THROTTLER.debounce(() => {
        const currentElement = document.activeElement.tagName;
        if (
          shortcuts !== HitShortcuts.NO_SHORTCUTS &&
          event.key.toUpperCase() in customActions &&
          !event.ctrlKey &&
          currentElement !== 'INPUT'
        ) {
          customActions[event.key.toUpperCase()]();
        }
      });
    },
    [customActions, shortcuts]
  );

  useEffect(() => {
    if (!isMobile) {
      window.addEventListener('keydown', keyboardDownHandler);

      return () => window.removeEventListener('keydown', keyboardDownHandler);
    }
  }, [keyboardDownHandler]);

  useEffect(() => {
    (async () => {
      setAnalytic(await getAnalyticFromName(hit.howler.analytic));
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hit.howler.analytic]);

  const handleOpenSetting = useCallback((e: React.MouseEvent<HTMLElement>) => setOpenSetting(e.currentTarget), []);
  const handleCloseSetting = useCallback(() => setOpenSetting(null), []);
  const onShortcutChange = useCallback((__: any, s: HitShortcuts) => set(StorageKey.HIT_SHORTCUTS, s), [set]);
  const onDropdownChange = useCallback((__: any, checked: boolean) => set(StorageKey.FORCE_DROPDOWN, checked), [set]);

  const showButton = useMediaQuery(
    // Only show the buttons when there's sufficient space
    // TODO: Could probably make this fancier and maybe remove the react device detect dependency, but this is fine for now
    json2mq([
      {
        minWidth: 1800
      }
    ])
  );

  const showDropdown = isMobile || !showButton;

  const actions =
    showDropdown || forceDropdown ? (
      <DropdownActions
        availableTransitions={availableTransitions}
        canAssess={canAssess}
        canVote={canVote}
        currentAssessment={hit?.howler.assessment}
        currentStatus={hit?.howler.status}
        customActions={customActions}
        loading={loading}
        orientation={orientation}
        selectedVote={selectedVote}
        validAssessments={analytic?.triage_settings?.valid_assessments}
        vote={vote}
      />
    ) : (
      <ButtonActions
        availableTransitions={availableTransitions}
        canAssess={canAssess}
        canVote={canVote}
        customActions={customActions}
        loading={loading}
        orientation={orientation}
        selectedVote={selectedVote}
        shortcuts={shortcuts}
        validAssessments={analytic?.triage_settings?.valid_assessments}
        vote={vote}
      />
    );

  return (
    <Stack direction="row" alignItems="stretch">
      {actions}
      {(!showDropdown || !isMobile) && (
        <Box
          sx={[
            {
              flex: 1,
              alignSelf: 'start',
              display: 'flex',
              justifyContent: 'end',
              alignItems: 'center',
              p: 1
            },
            (showDropdown || forceDropdown) && { flexDirection: 'column-reverse', justifyContent: 'center' },
            !showDropdown &&
              !forceDropdown && {
                position: 'absolute',
                top: 0,
                right: 0
              }
          ]}
        >
          <CircularProgress
            size={24}
            sx={theme => ({
              // Sneaky trick: +true === 1, +false === 0. Love you, javascript <3
              opacity: +loading,
              transition: `${theme.transitions.duration.standard}ms`
            })}
          />
          {!showDropdown && (
            <IconButton size="small" onClick={handleOpenSetting}>
              <MoreHoriz />
            </IconButton>
          )}
          <Menu
            anchorEl={openSetting}
            open={!!openSetting}
            onClose={handleCloseSetting}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            PaperProps={{
              sx: {
                '& ul': {
                  p: 2,
                  display: 'flex',
                  flexDirection: 'column'
                }
              }
            }}
          >
            <Stack spacing={1} divider={<Divider orientation="horizontal" />}>
              <FormControl>
                <FormLabel>
                  <Trans i18nKey="hit.details.shortcuts" />
                </FormLabel>
                <RadioGroup value={shortcuts} name="radio-buttons-group" onChange={onShortcutChange}>
                  <FormControlLabel
                    value={HitShortcuts.SHORTCUTS_HINT}
                    control={<Radio />}
                    label={<Trans i18nKey="hit.search.keyboard.shortcuts_hints" />}
                  />
                  <FormControlLabel
                    value={HitShortcuts.SHORTCUTS}
                    control={<Radio />}
                    label={<Trans i18nKey="hit.search.keyboard.shortcuts" />}
                  />
                  <FormControlLabel
                    value={HitShortcuts.NO_SHORTCUTS}
                    control={<Radio />}
                    label={<Trans i18nKey="hit.search.keyboard.no_shortcuts" />}
                  />
                </RadioGroup>
              </FormControl>
              <FormControl sx={{ display: 'flex', flexDirection: 'row', alignItems: 'center' }}>
                <FormLabel sx={{ mr: 1 }}>
                  <Trans i18nKey="hit.details.forceDropdown" />
                </FormLabel>
                <Switch checked={forceDropdown} onChange={onDropdownChange} />
              </FormControl>
            </Stack>
          </Menu>
        </Box>
      )}
    </Stack>
  );
};

export default memo(HitActions);
