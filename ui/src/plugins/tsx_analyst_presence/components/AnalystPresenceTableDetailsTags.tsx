import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import type { TagCategory, UserTags } from 'api/tags';
import { useTranslation } from 'react-i18next';
import { useAnalystPresenceFilters } from '../hooks/useAnalystPresenceFilters';

type AnalystPresenceTableDetailsTagsProps = {
  tags: UserTags | undefined;
};

const TAG_LABELS: Record<TagCategory, string> = {
  portfolio: 'tsxAnalystPresence.common.portfolio',
  products: 'tsxAnalystPresence.common.products',
  primary_disciplines: 'tsxAnalystPresence.common.disciplines'
};

export const AnalystPresenceTableDetailsTags = ({ tags }: AnalystPresenceTableDetailsTagsProps) => {
  const { t } = useTranslation();
  const { tagsOptions, toggleTagFilter, activeTagFilters } = useAnalystPresenceFilters();

  return (
    <Stack gap={2}>
      <Typography variant="subtitle1" fontWeight="bold">
        {t('tsxAnalystPresence.tags')}
      </Typography>

      {Object.entries(TAG_LABELS).map(([category, label]) => {
        const categoryTags = tags?.[category as TagCategory] || [];
        const tagsCount = categoryTags.length;

        return (
          <Box key={category} sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t(label)} ({tagsCount})
            </Typography>

            <Box flexWrap="wrap" display="flex" gap={0.5} mt={1}>
              {categoryTags.map(value => (
                <Chip
                  key={value}
                  label={tagsOptions[value] || value}
                  title={t('tsxAnalystPresence.tags.chip.tooltip')}
                  size="small"
                  color={activeTagFilters?.[category as TagCategory]?.includes(value) ? 'primary' : 'default'}
                  onClick={() => toggleTagFilter(category as TagCategory, value)}
                />
              ))}
            </Box>
          </Box>
        );
      })}
    </Stack>
  );
};
