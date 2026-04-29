import { FilterList } from '@mui/icons-material';
import { ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import ChipPopper from 'components/elements/display/ChipPopper';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { CASE_STATUSES } from '../constants';

const CaseStatusFilter: FC<{
  statusFilter: string[];
  onChange: (v: string[]) => void;
}> = ({ statusFilter, onChange }) => {
  const { t } = useTranslation();

  return (
    <ChipPopper
      icon={<FilterList fontSize="small" />}
      label={
        <Typography variant="body2">
          {statusFilter.length === 0
            ? t('route.cases.filter.status')
            : statusFilter.map(s => t(`page.cases.status.${s}`)).join(', ')}
        </Typography>
      }
      minWidth="200px"
      slotProps={{ chip: { size: 'small', color: statusFilter.length > 0 ? 'primary' : 'default' } }}
    >
      <ToggleButtonGroup
        value={statusFilter}
        onChange={(_, nv: string[]) => onChange(nv)}
        size="small"
        orientation="vertical"
        sx={{ width: '100%' }}
      >
        {CASE_STATUSES.map(s => (
          <ToggleButton key={s} value={s} sx={{ justifyContent: 'flex-start' }}>
            {t(`page.cases.status.${s}`)}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </ChipPopper>
  );
};

export default CaseStatusFilter;
