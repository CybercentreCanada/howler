/**
 * Displays the user preference toggle for grouping similar pivots together.
 * The switch reads and updates the shared pivot-grouping preference from local storage.
 */
import { List, ListItem, ListItemButton, ListItemText, Switch } from '@mui/material';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { FC, MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { StorageKey } from 'utils/constants';

const PivotGroupMenuItem: FC = () => {
  const { t } = useTranslation();
  const [pivotGroupEnabled, setPivotGroupEnabled] = useMyLocalStorageItem(StorageKey.PIVOT_GROUP, true);

  return (
    <List dense>
      <ListItem
        disablePadding
        secondaryAction={
          <Switch
            checked={pivotGroupEnabled}
            edge="end"
            onChange={() => setPivotGroupEnabled(!pivotGroupEnabled)}
            onClick={(event: MouseEvent<HTMLButtonElement>) => {
              event.stopPropagation();
            }}
          />
        }
      >
        <ListItemButton id="personalization-pivot-group" onClick={() => setPivotGroupEnabled(!pivotGroupEnabled)}>
          <ListItemText>{t('personalization.pivotGroup')}</ListItemText>
        </ListItemButton>
      </ListItem>
    </List>
  );
};

export default PivotGroupMenuItem;
