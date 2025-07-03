import type { StyledComponent } from '@emotion/styled';
import {
  Badge,
  Button,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Stack,
  styled,
  Tooltip,
  type BadgeProps
} from '@mui/material';
import { blueGrey } from '@mui/material/colors';
import type { FC } from 'react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { HitShortcuts } from '../HitShortcuts';
import type { ActionButton } from './SharedComponents';
import { TOP_ROW } from './SharedComponents';

interface DesktopActionProps {
  actions: ActionButton[];
  loading: boolean;
  shortcuts: HitShortcuts;
  currentVote: string;
  orientation: 'horizontal' | 'vertical';
}

const StyledBadge: StyledComponent<BadgeProps> = styled(Badge)({
  '& .MuiBadge-badge': {
    borderRadius: '4px',
    background: blueGrey[400],
    fontSize: 9,
    height: '15px',
    minWidth: '15px',
    padding: '0',
    right: '5px',
    top: '2.5px'
  }
});

const ButtonActions: FC<DesktopActionProps> = ({ actions, loading, orientation, shortcuts, currentVote }) => {
  const { t } = useTranslation();

  const isHorizontal = useMemo(() => orientation === 'horizontal', [orientation]);
  const showShortcuts = useMemo(() => shortcuts === HitShortcuts.SHORTCUTS_HINT, [shortcuts]);

  const actionRows = useMemo(
    () =>
      actions
        .filter(action => action.type === 'action')
        .reduce(
          ([top, bottom], action) => {
            if (top.length === bottom.length) {
              top.push(action);
            } else {
              bottom.push(action);
            }

            return [top, bottom];
          },
          [[], []] as [ActionButton[], ActionButton[]]
        ),
    [actions]
  );

  const assessmentRows = useMemo(
    () =>
      actions
        .filter(action => action.type === 'assessment')
        .reduce(
          ([top, bottom], action) => {
            if (TOP_ROW.includes(action.name)) {
              top.push(action);
            } else {
              bottom.push(action);
            }

            return [top, bottom];
          },
          [[], []] as [ActionButton[], ActionButton[]]
        ) ?? [],
    [actions]
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
                gridAutoColumns: 'minmax(0, 125px)', // Make sure the buttons are the same width
                // God help me
                gridTemplateColumns: `repeat(auto, 125px)`
                // Why do we need to use both gridTemplateColumns AND gridAutoColumns, you ask?
                // I DON'T KNOW ASK WHOEVER WROTE THE CSS GRID SPEC
              }
            : {
                gridTemplateColumns: '1fr 1fr'
              }
        ]}
      >
        <FormLabel>{t('hit.details.actions.action')}</FormLabel>
        {actionRows.flatMap((row, rowIndex) =>
          row.map((option, index) => {
            const gridSx = isHorizontal
              ? { gridColumn: index, gridRow: rowIndex + 2 }
              : { gridColumn: rowIndex + 1, gridRow: index + 2 };

            const button = (
              <Button
                size="small"
                variant="outlined"
                color="secondary"
                disabled={loading}
                key={option.name}
                onClick={option.actionFunction}
                sx={[
                  {
                    width: '100%',
                    p: 0.6
                  },
                  gridSx,
                  isHorizontal && (theme => ({ fontSize: theme.typography.caption.fontSize }))
                ]}
              >
                {option.i18nKey ? t(option.i18nKey) : option.name}
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
          })
        )}
        {assessmentRows.flat().length > 0 && (
          <FormLabel
            sx={
              isHorizontal
                ? {
                    gridRow: 1,
                    gridColumn: actionRows[0].length + 1
                  }
                : { gridRow: actionRows[0].length + 2 }
            }
          >
            {t('hit.details.actions.assessment')}
          </FormLabel>
        )}
        {assessmentRows.flatMap((row, rowIndex) =>
          row.map((action, index) => {
            const gridSx = isHorizontal
              ? {
                  gridColumn: index + 1 + actionRows[0].length,
                  gridRow: rowIndex + 2
                }
              : { gridColumn: rowIndex + 1, gridRow: index + 3 + actionRows[0].length };

            const button = (
              <Tooltip title={t(`hit.details.asessments.${action.name}.description`)}>
                <Button
                  key={action.name}
                  variant="outlined"
                  size="small"
                  disabled={loading}
                  onClick={action.actionFunction}
                  sx={[
                    {
                      width: '100%',
                      p: 0.6
                    },
                    gridSx,
                    isHorizontal && (theme => ({ fontSize: theme.typography.caption.fontSize }))
                  ]}
                >
                  {action.name}
                </Button>
              </Tooltip>
            );

            if (showShortcuts) {
              return (
                <StyledBadge badgeContent={action.key} key={action.key} sx={gridSx}>
                  {button}
                </StyledBadge>
              );
            }

            return button;
          })
        )}
      </FormControl>
      <FormControl
        disabled={loading || !actions.some(action => action.type === 'vote')}
        sx={{ opacity: +actions.some(action => action.type === 'vote') }}
      >
        <FormLabel sx={{ mb: 1 }}>{t('hit.details.actions.vote')}</FormLabel>
        <RadioGroup value={currentVote}>
          {actions
            .filter(action => action.type === 'vote')
            .map(action => {
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
                  onClick={action.actionFunction}
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
