import { ArrowDropDown, List, Settings, TableChart, ViewComfy, ViewCompact, ViewModule } from '@mui/icons-material';
import { FormLabel, Stack, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { HitSearchContext } from 'components/app/providers/HitSearchProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';

const LayoutSettings: FC = () => {
  const { t } = useTranslation();

  const displayType = useContextSelector(HitSearchContext, ctx => ctx.displayType);
  const setDisplayType = useContextSelector(HitSearchContext, ctx => ctx.setDisplayType);
  const [hitLayout, setHitLayout] = useMyLocalStorageItem(StorageKey.HIT_LAYOUT, false);

  return (
    <ChipPopper
      icon={<Settings />}
      deleteIcon={<ArrowDropDown />}
      toggleOnDelete
      disablePortal={false}
      slotProps={{ chip: { size: 'medium' } }}
      placement="bottom-end"
    >
      <Stack spacing={1}>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
          <FormLabel>{t('page.settings.local.hits.display_type')}</FormLabel>
          <ToggleButtonGroup exclusive value={displayType} onChange={(__, value) => setDisplayType(value)} size="small">
            <ToggleButton value="list">
              <Stack direction="row" spacing={0.5}>
                <List />
                <span>{t('page.settings.local.hits.display_type.list')}</span>
              </Stack>
            </ToggleButton>
            <ToggleButton value="grid">
              <Stack direction="row" spacing={0.5}>
                <TableChart />
                <span>{t('page.settings.local.hits.display_type.grid')}</span>
              </Stack>
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
          <FormLabel>{t('page.settings.local.hits.layout')}</FormLabel>
          <ToggleButtonGroup exclusive size="small" value={hitLayout} onChange={(_, value) => setHitLayout(value)}>
            <ToggleButton value={HitLayout.DENSE}>
              <Stack direction="row" spacing={0.5}>
                <ViewCompact />
                <span>{t('page.settings.local.hits.layout.dense')}</span>
              </Stack>
            </ToggleButton>
            <ToggleButton value={HitLayout.NORMAL}>
              <Stack direction="row" spacing={0.5}>
                <ViewModule />
                <span>{t('page.settings.local.hits.layout.normal')}</span>
              </Stack>
            </ToggleButton>
            <ToggleButton value={HitLayout.COMFY}>
              <Stack direction="row" spacing={0.5}>
                <ViewComfy />
                <span>{t('page.settings.local.hits.layout.comfy')}</span>
              </Stack>
            </ToggleButton>
          </ToggleButtonGroup>
        </Stack>
      </Stack>
    </ChipPopper>
  );
};

export default LayoutSettings;
