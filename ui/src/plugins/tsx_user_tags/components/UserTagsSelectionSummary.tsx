import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import type { TagCategory, TagsDictionary, UserTags } from 'api/tags';
import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { TAG_CATEGORY_OPTIONS } from '../userTags.constants';

type UserTagsSelectionSummaryProps = {
  tagsDictionary: TagsDictionary;
  selectedTags: UserTags;
  onRemoveTag: (category: TagCategory, value: string) => void;
  onClearCategory: (category: TagCategory) => void;
};

export const UserTagsSelectionSummary = ({
  tagsDictionary,
  selectedTags,
  onRemoveTag,
  onClearCategory
}: UserTagsSelectionSummaryProps) => {
  const { t } = useTranslation();

  const handleRemoveTag = useCallback(
    (category: TagCategory, value: string) => {
      onRemoveTag(category, value);
    },
    [onRemoveTag]
  );

  return (
    <Stack flex={0.8} sx={{ borderLeft: '1px solid', borderColor: 'divider' }}>
      <Stack
        sx={{
          py: 1.5,
          px: 2,
          gap: 6,
          flex: 1,
          overflowY: 'auto',
          scrollbarWidth: 'thin'
        }}
      >
        {TAG_CATEGORY_OPTIONS.map(option => {
          const entries = tagsDictionary[option.value];
          const selectedEntries = entries.filter(tag => selectedTags[option.value].includes(tag.value));

          return (
            <Box key={option.value}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  pb: 1,
                  mb: 2,
                  borderBottom: '1px solid',
                  borderColor: 'divider'
                }}
              >
                <Typography variant="subtitle2" fontWeight={600} sx={{ textTransform: 'capitalize' }}>
                  {t(option.labelKey)} ({selectedEntries.length})
                </Typography>

                <Button
                  variant="text"
                  color="error"
                  size="small"
                  title={t('tsxUserTags.drawer.clearButton.tooltip')}
                  onClick={() => onClearCategory(option.value)}
                  disabled={selectedEntries.length === 0}
                >
                  {t('tsxUserTags.drawer.clearButton')}
                </Button>
              </Box>

              <Stack direction="row" flexWrap="wrap" columnGap={0.5} rowGap={1}>
                {selectedEntries.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    {t('tsxUserTags.drawer.noSelection')}
                  </Typography>
                ) : (
                  selectedEntries.map(tag => (
                    <Chip
                      key={tag.value}
                      size="small"
                      label={tag.name}
                      onDelete={() => handleRemoveTag(option.value, tag.value)}
                    />
                  ))
                )}
              </Stack>
            </Box>
          );
        })}
      </Stack>
    </Stack>
  );
};
