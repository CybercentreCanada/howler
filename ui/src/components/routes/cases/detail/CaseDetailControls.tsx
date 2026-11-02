import { Check, HourglassBottom, Pause, TrendingUp, WarningRounded } from '@mui/icons-material';
import { Autocomplete, Stack, TextField, Typography } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { ESCALATION_COLOR_MAP } from '../constants';

interface CaseStatusControlProps {
  value?: string;
  options: string[];
  disabled?: boolean;
  onChange: (status: string) => void;
}

export const CaseStatusControl: FC<CaseStatusControlProps> = ({ value, options, disabled = false, onChange }) => {
  const { t } = useTranslation();

  return (
    <Stack spacing={1}>
      <Stack direction="row" spacing={1} alignItems="center">
        {{
          'in-progress': <HourglassBottom color="warning" />,
          'on-hold': <Pause color="disabled" />,
          resolved: <Check color="success" />
        }[value ?? ''] ?? <WarningRounded fontSize="small" />}
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

interface CaseEscalationControlProps {
  value?: string;
  options: string[];
  disabled?: boolean;
  onChange: (escalation: string) => void;
}

export const CaseEscalationControl: FC<CaseEscalationControlProps> = ({
  value,
  options,
  disabled = false,
  onChange
}) => {
  const { t } = useTranslation();
  const escalationColor = ESCALATION_COLOR_MAP[value as keyof typeof ESCALATION_COLOR_MAP];
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
