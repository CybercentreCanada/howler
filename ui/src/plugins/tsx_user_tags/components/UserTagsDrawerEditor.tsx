import { Close as CloseIcon, Search as SearchIcon } from '@mui/icons-material';
import {
  Box,
  Checkbox,
  FormControlLabel,
  IconButton,
  InputAdornment,
  OutlinedInput,
  Stack,
  Tab,
  Tabs,
  Typography
} from '@mui/material';
import type { TagCategory, TagsDictionary, UserTags } from 'api/tags';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TAG_CATEGORY_OPTIONS } from '../userTags.constants';
import { UserTagsSelectionSummary } from './UserTagsSelectionSummary';

type UserTagsDrawerEditorProps = {
  tagsDictionary: TagsDictionary;
  selectedTags: UserTags;
  onChange: (category: TagCategory, tags: string[]) => void;
  onSearchFocusChange: (isFocused: boolean) => void;
};

export const UserTagsDrawerEditor = ({
  tagsDictionary,
  selectedTags,
  onChange,
  onSearchFocusChange
}: UserTagsDrawerEditorProps) => {
  const { t } = useTranslation();

  const [activeCategory, setActiveCategory] = useState<TagCategory>('portfolio');
  const [keyword, setKeyword] = useState('');

  const activeTags = useMemo(() => tagsDictionary[activeCategory], [tagsDictionary, activeCategory]);
  const activeSelectedTags = useMemo(() => selectedTags[activeCategory], [selectedTags, activeCategory]);

  const filteredTags = useMemo(() => {
    if (!keyword.trim()) return activeTags;

    return activeTags.filter(tag => tag.name.toLowerCase().includes(keyword.toLowerCase()));
  }, [activeTags, keyword]);

  const handleToggleTag = useCallback(
    (value: string) => {
      const isSelected = activeSelectedTags.includes(value);
      const newSelectedTags = isSelected
        ? activeSelectedTags.filter(tag => tag !== value)
        : [...activeSelectedTags, value];
      onChange(activeCategory, newSelectedTags);
    },
    [activeCategory, activeSelectedTags, onChange]
  );

  const handleRemoveTag = useCallback(
    (category: TagCategory, value: string) => {
      const currentTags = selectedTags[category];
      onChange(
        category,
        currentTags.filter(tag => tag !== value)
      );
    },
    [selectedTags, onChange]
  );

  const handleClearCategory = useCallback(
    (category: TagCategory) => {
      onChange(category, []);
    },
    [onChange]
  );

  useEffect(() => {
    setKeyword('');
  }, [activeCategory]);

  return (
    <Box sx={{ display: 'flex', flex: 1, overflowY: 'hidden' }}>
      <Stack flex={1}>
        <Stack
          alignItems="center"
          sx={{ pt: 0.5, pb: 2.5, px: 1.5, gap: 2, borderBottom: '1px solid', borderColor: 'divider' }}
        >
          <Tabs
            variant="fullWidth"
            textColor="inherit"
            value={activeCategory}
            onChange={(_, newValue) => setActiveCategory(newValue)}
            sx={{ width: '100%' }}
          >
            {TAG_CATEGORY_OPTIONS.map(option => (
              <Tab key={option.value} label={t(option.labelKey)} value={option.value} />
            ))}
          </Tabs>

          <OutlinedInput
            placeholder={t('tsxUserTags.drawer.searchLabel')}
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => e.key === 'Escape' && setKeyword('')}
            onFocus={() => onSearchFocusChange(true)}
            onBlur={() => onSearchFocusChange(false)}
            size="small"
            fullWidth
            startAdornment={
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            }
            endAdornment={
              keyword && (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => setKeyword('')}
                    aria-label={t('tsxUserTags.drawer.clearSearch')}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              )
            }
          />
        </Stack>

        <Stack
          sx={{
            py: 1,
            px: 2,
            flex: 1,
            overflowY: 'auto',
            scrollbarWidth: 'thin'
          }}
        >
          {filteredTags.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {t('tsxUserTags.drawer.noResults')}
            </Typography>
          ) : (
            filteredTags.map(tag => (
              <FormControlLabel
                key={tag.value}
                label={tag.name}
                sx={{
                  mr: 0,
                  borderRadius: 1,
                  '&:hover': { bgcolor: 'action.hover' }
                }}
                control={
                  <Checkbox
                    checked={activeSelectedTags.includes(tag.value)}
                    onChange={() => handleToggleTag(tag.value)}
                  />
                }
              />
            ))
          )}
        </Stack>
      </Stack>

      <UserTagsSelectionSummary
        tagsDictionary={tagsDictionary}
        selectedTags={selectedTags}
        onRemoveTag={handleRemoveTag}
        onClearCategory={handleClearCategory}
      />
    </Box>
  );
};
