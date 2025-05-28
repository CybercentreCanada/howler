import { Button, FormControl, FormControlLabel, FormLabel, Radio, RadioGroup, Stack, Tooltip } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { HitShortcuts } from '../HitShortcuts';
import type { ActionButton } from './SharedComponents';
import { ASSESSMENT_KEYBINDS, StyledBadge, TOP_ROW, VOTE_OPTIONS } from './SharedComponents';

interface DesktopActionProps {
  availableTransitions: ActionButton[];
  canVote: boolean;
  canAssess: boolean;
  customActions: { [index: string]: () => void };
  loading: boolean;
  orientation: 'horizontal' | 'vertical';
  selectedVote: ActionButton['name'];
  shortcuts: HitShortcuts;
  validAssessments: string[];
  vote: (v: string) => void;
}

const ButtonActions: FC<DesktopActionProps> = ({
  availableTransitions,
  canAssess,
  canVote,
  customActions,
  loading,
  orientation,
  selectedVote,
  validAssessments,
  shortcuts,
  vote
}) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  const isHorizontal = useMemo(() => orientation === 'horizontal', [orientation]);
  const showShortcuts = useMemo(() => shortcuts === HitShortcuts.SHORTCUTS_HINT, [shortcuts]);

  const assessmentRows = useMemo(
    () =>
      config.lookups?.['howler.assessment']
        .filter(_assessment => (validAssessments ? validAssessments.includes(_assessment) : true))
        .reduce(
          ([top, bottom], assessment) => {
            if (TOP_ROW.includes(assessment)) {
              top.push(assessment);
            } else {
              bottom.push(assessment);
            }

            return [top, bottom];
          },
          [[], []] as [string[], string[]]
        ) ?? [],
    [config.lookups, validAssessments]
  );

  return (
    <Stack
      direction={isHorizontal ? 'row' : 'column'}
      spacing={0.75}
      alignItems={!isHorizontal && 'start'}
      py={1}
      sx={{ position: 'relative', flex: 1 }}
      justifyContent="space-between"
    >
      <FormControl
        disabled={loading}
        sx={[
          {
            display: 'grid',
            justifyContent: 'stretch',
            gap: 0.8
          },
          isHorizontal
            ? {
                // If you want to understand the disgusting, unholy grid shenanigans that's going on here, talk to Matt R
                // If you want to complain about how bad this is, talk to Ben
                gridTemplateRows: 'auto 1fr 1fr', // Make sure the buttons are the same height
                gridAutoColumns: 'minmax(0, 1fr)', // Make sure the buttons are the same width
                // God help me
                gridTemplateColumns: `repeat(${Math.ceil(availableTransitions.length / 2)}, minmax(0, 1fr)) 0` // This sets the (n + 1)th column
                // (the spacer between actions and assessments) to 0 where n is the number of columns used up by the available transitions
                // Why do we need to use both gridTemplateColumns AND gridAutoColumns, you ask?
                // I DON'T KNOW ASK WHOEVER WROTE THE CSS GRID SPEC
              }
            : {
                gridTemplateColumns: '1fr 1fr'
              }
        ]}
      >
        <FormLabel>{t('hit.details.actions.transition')}</FormLabel>
        {availableTransitions.map((option, index) => {
          const gridSx = isHorizontal
            ? { gridColumn: Math.floor(index / 2 + 1), gridRow: (index % 2) + 2 }
            : { gridColumn: (index % 2) + 1, gridRow: Math.floor(index / 2 + 2) };

          const button = (
            <Button
              size="small"
              variant="outlined"
              color="secondary"
              disabled={loading}
              key={option.name}
              onClick={customActions[option.key]}
              sx={[
                {
                  width: '100%',
                  p: 0.6
                },
                gridSx,
                isHorizontal && (theme => ({ fontSize: theme.typography.caption.fontSize }))
              ]}
            >
              {t(`hit.details.actions.transition.${option.name}`)}
            </Button>
          );

          if (showShortcuts) {
            return (
              <StyledBadge badgeContent={option.key} key={option.name} sx={gridSx}>
                {button}
              </StyledBadge>
            );
          }

          return button;
        })}
        {canAssess && (
          <FormLabel
            sx={
              isHorizontal
                ? { gridRow: 1, gridColumn: Math.ceil(availableTransitions.length / 2 + 2) }
                : { gridRow: Math.ceil(availableTransitions.length / 2 + 2) }
            }
          >
            {t('hit.details.actions.assess')}
          </FormLabel>
        )}
        {canAssess &&
          assessmentRows.flatMap((row, rowIndex, rows) =>
            row.map((assessment, index) => {
              const totalIndex = rows[0].length * rowIndex + index;

              const gridSx = isHorizontal
                ? {
                    gridColumn: index + 2 + Math.ceil(availableTransitions.length / 2),
                    gridRow: rowIndex + 2
                  }
                : { gridColumn: rowIndex + 1, gridRow: index + 3 + Math.ceil(availableTransitions.length / 2) };

              const button = (
                <Tooltip title={t(`hit.details.asessments.${assessment}.description`)}>
                  <Button
                    key={assessment}
                    variant="outlined"
                    size="small"
                    disabled={loading}
                    onClick={customActions[ASSESSMENT_KEYBINDS[totalIndex]]}
                    sx={[
                      {
                        width: '100%',
                        p: 0.6
                      },
                      gridSx,
                      isHorizontal && (theme => ({ fontSize: theme.typography.caption.fontSize }))
                    ]}
                  >
                    {assessment}
                  </Button>
                </Tooltip>
              );

              if (showShortcuts) {
                return (
                  <StyledBadge badgeContent={ASSESSMENT_KEYBINDS[totalIndex]} key={assessment} sx={gridSx}>
                    {button}
                  </StyledBadge>
                );
              }

              return button;
            })
          )}
      </FormControl>
      <FormControl disabled={loading || !canVote} sx={{ opacity: +canVote }}>
        <FormLabel sx={{ mb: 1 }}>{t('hit.details.actions.vote')}</FormLabel>
        <RadioGroup value={selectedVote} onChange={e => vote(e.currentTarget.value)}>
          {VOTE_OPTIONS.map(action => {
            const button = (
              <FormControlLabel
                key={action.key}
                value={action.name.toLowerCase()}
                sx={{ display: 'flex', alignItems: 'center' }}
                componentsProps={{
                  typography: {
                    sx: [isHorizontal && (theme => ({ fontSize: theme.typography.caption.fontSize }))]
                  }
                }}
                control={<Radio size="small" sx={[{ mr: 1 }, isHorizontal && { p: 0.5 }]} />}
                label={action.name}
              />
            );

            if (showShortcuts && action.key) {
              return (
                <StyledBadge
                  badgeContent={action.key}
                  key={action.key}
                  sx={[
                    { '& .MuiBadge-badge': { left: '20px', top: '5px', right: 'unset' } },
                    loading && { '.MuiBadge-badge': { opacity: '0.5' } }
                  ]}
                  anchorOrigin={{
                    vertical: 'top',
                    horizontal: 'left'
                  }}
                >
                  {button}
                </StyledBadge>
              );
            }

            return button;
          })}
        </RadioGroup>
      </FormControl>
    </Stack>
  );
};

export default ButtonActions;
