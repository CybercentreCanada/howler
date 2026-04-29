import {
  ArrowDropDown,
  InfoOutlined,
  List,
  Settings,
  TableChart,
  ViewComfy,
  ViewCompact,
  ViewModule
} from '@mui/icons-material';
import {
  Checkbox,
  Divider,
  FormLabel,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip
} from '@mui/material';
import { RecordSearchContext } from 'components/app/providers/RecordSearchProvider';
import ChipPopper from 'components/elements/display/ChipPopper';
import { HitLayout } from 'components/elements/hit/HitLayout';
import { useMyLocalStorageItem } from 'components/hooks/useMyLocalStorage';
import type { FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useContextSelector } from 'use-context-selector';
import { StorageKey } from 'utils/constants';

const LayoutSettings: FC = () => {
  const { t } = useTranslation();

  const displayType = useContextSelector(RecordSearchContext, ctx => ctx.displayType);
  const setDisplayType = useContextSelector(RecordSearchContext, ctx => ctx.setDisplayType);
  const [hitLayout, setHitLayout] = useMyLocalStorageItem(StorageKey.HIT_LAYOUT, false);
  const [templateFieldCount, setTemplateFieldCount] = useMyLocalStorageItem(StorageKey.TEMPLATE_FIELD_COUNT, null);

  return (
    <ChipPopper
      icon={
        <Tooltip title={t('search.layout.settings')}>
          <Settings />
        </Tooltip>
      }
      deleteIcon={<ArrowDropDown />}
      toggleOnDelete
      disablePortal={false}
      slotProps={{ chip: { size: 'medium', 'aria-label': t('search.layout.settings') } }}
      placement="bottom-end"
    >
      <Stack spacing={1} alignItems="start">
        <Stack direction="row" spacing={0.5} alignItems="center" alignSelf="stretch">
          <FormLabel id="display_type">{t('page.settings.local.hits.display_type')}</FormLabel>
          <div style={{ flex: 1 }} />
          <Tooltip title={t('page.settings.local.hits.display_type.description')}>
            <InfoOutlined fontSize="inherit" />
          </Tooltip>
        </Stack>
        <ToggleButtonGroup
          exclusive
          value={displayType}
          onChange={(__, value) => setDisplayType(value)}
          size="small"
          aria-labelledby="display_type"
        >
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
        <Divider flexItem />
        <Stack direction="row" spacing={0.5} alignItems="center" alignSelf="stretch">
          <FormLabel id="layout">{t('page.settings.local.hits.layout')}</FormLabel>
          <div style={{ flex: 1 }} />
          <Tooltip title={t('page.settings.local.hits.layout.description')}>
            <InfoOutlined fontSize="inherit" />
          </Tooltip>
        </Stack>
        <ToggleButtonGroup
          exclusive
          size="small"
          value={hitLayout}
          onChange={(_, value) => setHitLayout(value)}
          aria-labelledby="layout"
        >
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
        <Divider flexItem />
        <Stack direction="row" spacing={0.5} alignItems="center" alignSelf="stretch">
          <FormLabel id="field_count">{t('page.settings.local.hits.field_count')}</FormLabel>
          <div style={{ flex: 1 }} />
          <Tooltip title={t('page.settings.local.hits.field_count.description')}>
            <InfoOutlined fontSize="inherit" />
          </Tooltip>
        </Stack>
        <Stack direction="row" spacing={0.5} alignSelf="stretch">
          <Checkbox
            checked={templateFieldCount !== null}
            onChange={(_, checked) => setTemplateFieldCount(checked ? 3 : null)}
            size="small"
          />
          <TextField
            type="number"
            size="small"
            disabled={templateFieldCount === null}
            value={templateFieldCount ?? 3}
            fullWidth
            onChange={e => {
              const val = parseInt(e.target.value);
              if (!isNaN(val)) {
                setTemplateFieldCount(Math.min(15, Math.max(0, val)));
              }
            }}
            inputProps={{ min: 0, max: 15, 'aria-labelledby': 'field_count' }}
          />
        </Stack>
      </Stack>
    </ChipPopper>
  );
};

export default LayoutSettings;
