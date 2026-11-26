import { Check, HourglassBottom, Pause, TrendingUp, WarningRounded } from '@mui/icons-material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import type { Case } from 'models/entities/generated/Case';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { ESCALATION_COLOR_MAP } from '../constants';

interface CaseControlProps<T extends string> {
  value?: T;
  options: T[];
  disabled?: boolean;
  onChange: (value: T) => void;
}

export const CaseStatusControl: FC<CaseControlProps<NonNullable<Case['status']>>> = ({
  value,
  options,
  disabled = false,
  onChange
}) => {
  const { t } = useTranslation();

  return (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} alignItems="center">
        {
          {
            open: <WarningRounded fontSize="small" />,
            'in-progress': <HourglassBottom color="warning" />,
            'on-hold': <Pause color="disabled" />,
            resolved: <Check color="success" />
          }[value ?? 'open']
        }
        <Typography variant="body1">{t('page.cases.detail.status')}</Typography>
      </Stack>
      <Autocomplete
        size="small"
        disabled={disabled}
        disableClearable
        value={value}
        options={options}
        renderInput={params => <TextField {...params} size="small" />}
        onChange={(_ev, status) => status && onChange(status)}
      />
    </Stack>
  );
};

export const CaseEscalationControl: FC<CaseControlProps<NonNullable<Case['escalation']>>> = ({
  value,
  options,
  disabled = false,
  onChange
}) => {
  const { t } = useTranslation();
  const escalationColor = value && ESCALATION_COLOR_MAP[value];
  const escalationIconColor = escalationColor === 'default' ? 'inherit' : escalationColor;

  return (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} alignItems="center">
        <TrendingUp color={escalationIconColor} />
        <Typography variant="body1">{t('page.cases.detail.escalation')}</Typography>
      </Stack>
      <Autocomplete
        size="small"
        disabled={disabled}
        disableClearable
        value={value ?? undefined}
        options={options}
        renderInput={params => <TextField {...params} size="small" />}
        onChange={(_ev, escalation) => escalation && onChange(escalation)}
      />
    </Stack>
  );
};
