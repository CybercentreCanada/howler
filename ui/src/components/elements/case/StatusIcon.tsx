import { Check, HourglassBottom, Pause, Troubleshoot } from '@mui/icons-material';
import { Tooltip } from '@mui/material';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';

const StatusIcon: FC<{ status: string }> = ({ status }) => {
  const { t } = useTranslation();

  return (
    <Tooltip title={t(`page.cases.status.${status}`)}>
      {{
        'in-progress': <HourglassBottom color="warning" />,
        'on-hold': <Pause color="disabled" />,
        resolved: <Check color="success" />
      }[status] ?? <Troubleshoot color="primary" />}
    </Tooltip>
  );
};

export default StatusIcon;
