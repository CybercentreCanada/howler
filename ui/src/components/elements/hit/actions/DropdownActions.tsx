import {
  FormControl,
  formControlClasses,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Skeleton,
  Stack,
  Typography
} from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { capitalize } from 'lodash-es';
import type { FC } from 'react';
import { useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { ActionButton } from './SharedComponents';

interface DropdownActionProps {
  actions: ActionButton[];
  currentAssessment: string;
  currentStatus: string;
  currentVote: string;
  loading: boolean;
  orientation: 'horizontal' | 'vertical';
}

const DropdownActions: FC<DropdownActionProps> = ({
  actions,
  currentAssessment,
  currentStatus,
  currentVote,
  loading,
  orientation
}) => {
  const { t } = useTranslation();
  const config = useContext(ApiConfigContext);
  const isHorizontal = useMemo(() => orientation === 'horizontal', [orientation]);

  if (!config.config.lookups) {
    return (
      <Grid container justifyContent="end" spacing={4} p={2}>
        <Grid item sm="auto" xs={12}>
          <Skeleton variant="rounded" width="200px" height={orientation === 'horizontal' ? '40px' : '56px'}></Skeleton>
        </Grid>
        <Grid item sm="auto" xs={12}>
          <Skeleton variant="rounded" width="200px" height={orientation === 'horizontal' ? '40px' : '56px'}></Skeleton>
        </Grid>
        <Grid item sm="auto" xs={12}>
          <Skeleton variant="rounded" width="200px" height={orientation === 'horizontal' ? '40px' : '56px'}></Skeleton>
        </Grid>
      </Grid>
    );
  }

  return (
    <Grid
      container
      justifyContent="end"
      spacing={2}
      p={2}
      sx={[isHorizontal && { [`& .${formControlClasses.root}`]: { minWidth: '140px' } }]}
    >
      <Grid item sm={!isHorizontal ? true : 'auto'} xs={12}>
        <FormControl disabled={loading} fullWidth>
          <InputLabel id="transition-label" htmlFor="transition">
            {t('hit.details.actions.action')}
          </InputLabel>
          <Select
            labelId="transition-label"
            id="transition"
            size={isHorizontal ? 'small' : 'medium'}
            label={t('hit.details.actions.action')}
            value={currentStatus}
          >
            <MenuItem value={currentStatus} sx={{ display: 'none' }}>
              {currentStatus.replace(/-/g, ' ').replace(/^[a-z]/, val => val.toUpperCase())}
            </MenuItem>
            {actions
              .filter(_action => _action.type === 'action')
              .map(_action => (
                <MenuItem key={_action.name} value={_action.name} onClick={_action.actionFunction}>
                  {_action.i18nKey ? t(_action.i18nKey) : _action.name}
                </MenuItem>
              ))}
          </Select>
        </FormControl>
      </Grid>
      <Grid item sm={!isHorizontal ? true : 'auto'} xs={12}>
        <FormControl disabled={loading || !actions.some(action => action.type === 'assessment')} fullWidth>
          <InputLabel id="assess-label" htmlFor="assess">
            {t('hit.details.actions.assessment')}
          </InputLabel>
          <Select
            labelId="assess-label"
            id="assess"
            size={isHorizontal ? 'small' : 'medium'}
            label={t('hit.details.actions.assessment')}
            value={currentAssessment ?? 'no-assessment'}
            MenuProps={{
              anchorOrigin: { horizontal: 'left', vertical: 'bottom' },
              transformOrigin: { horizontal: 'left', vertical: 'top' }
            }}
          >
            <MenuItem value="no-assessment" sx={{ display: 'none' }}>
              {t('hit.details.actions.assessment.noassessment')}
            </MenuItem>
            {actions
              .filter(action => action.type === 'assessment')
              .map(a => (
                <MenuItem value={a.name} onClick={a.actionFunction} key={a.name}>
                  <Stack direction="column">
                    <span>
                      {a.name
                        .split(/[ -]/)
                        .map(part => capitalize(part))
                        .join(' ')}
                    </span>
                    <Typography variant="caption" color="text.secondary" maxWidth="250px" sx={{ whiteSpace: 'wrap' }}>
                      {t(`hit.details.asessments.${a.name}.description`)}
                    </Typography>
                  </Stack>
                </MenuItem>
              ))}
          </Select>
        </FormControl>
      </Grid>
      <Grid item sm={!isHorizontal ? true : 'auto'} xs={12}>
        <FormControl disabled={loading || !actions.some(action => action.type === 'vote')} fullWidth>
          <InputLabel id="vote-label" htmlFor="vote">
            {t('hit.details.actions.vote')}
          </InputLabel>
          <Select
            labelId="vote-label"
            id="vote"
            size={isHorizontal ? 'small' : 'medium'}
            label={t('hit.details.actions.vote')}
            value={currentVote || 'no-vote'}
          >
            <MenuItem value="no-vote" sx={{ display: 'none' }}>
              {t('hit.details.actions.vote.novote')}
            </MenuItem>
            {actions
              .filter(action => action.type === 'vote')
              .map(action => (
                <MenuItem key={action.name} value={action.name.toLowerCase()} onClick={action.actionFunction}>
                  {action.i18nKey ? t(action.i18nKey) : action.name}
                </MenuItem>
              ))}
          </Select>
        </FormControl>
      </Grid>
    </Grid>
  );
};

export default DropdownActions;
