import { ListItemButton, ListItemText, Switch } from '@mui/material';
import { usePivotGroup } from 'components/app/providers/PivotGroupProvider';
import type { FC, MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

const PivotGroupMenuItem: FC = () => {
  const { t } = useTranslation();
  const pivotGroup = usePivotGroup();

  const onSwitchClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
  };

  return (
    <ListItemButton onClick={pivotGroup.toggle} sx={{ width: '100%' }}>
      <ListItemText>{t('personalization.pivotGroup')}</ListItemText>
      <Switch checked={pivotGroup.enabled} edge="end" onChange={pivotGroup.toggle} onClick={onSwitchClick} />
    </ListItemButton>
  );
};

export default PivotGroupMenuItem;
