/**
 * Displays the user preference toggle for grouping similar pivots together.
 * The switch reads and updates the shared pivot-grouping state from the provider.
 */
import { ListItemButton, ListItemText, Switch } from '@mui/material';
import { usePivotGroup } from 'components/app/providers/PivotGroupProvider';
import type { FC, MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

const PivotGroupMenuItem: FC = () => {
  const { t } = useTranslation();
  const pivotGroup = usePivotGroup();

  /**
   * Prevents the row click from firing when the user toggles the switch.
   * This keeps the toggle interaction isolated from the parent menu item behavior.
   */
  const onSwitchClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
  };

  return (
    <ListItemButton id="personalization-pivot-group" onClick={pivotGroup.toggle} sx={{ width: '100%' }}>
      <ListItemText>{t('personalization.pivotGroup')}</ListItemText>
      <Switch checked={pivotGroup.enabled} edge="end" onChange={pivotGroup.toggle} onClick={onSwitchClick} />
    </ListItemButton>
  );
};

export default PivotGroupMenuItem;
