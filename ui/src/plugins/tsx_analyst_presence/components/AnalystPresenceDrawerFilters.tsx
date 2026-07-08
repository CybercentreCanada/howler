import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import type { TagCategory } from 'api/tags';
import { useTranslation } from 'react-i18next';
import { useAnalystPresenceFilters } from '../hooks/useAnalystPresenceFilters';

const STATUS_OPTIONS = ['available', 'unavailable', 'all'] as const;
const TAG_LABELS: Record<TagCategory, string> = {
  portfolio: 'tsxAnalystPresence.common.portfolio',
  products: 'tsxAnalystPresence.common.products',
  primary_disciplines: 'tsxAnalystPresence.common.disciplines'
};

const PAPER_ELEVATION = 15;

const TwoColumnGrid = ({ children }: { children: React.ReactNode }) => (
  <Box
    sx={{
      display: 'grid',
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: 2
    }}
  >
    {children}
  </Box>
);

export const AnalystPresenceDrawerFilters = () => {
  const { t } = useTranslation();
  const { activeStatusFilter, setStatusFilter, activeTagFilters, setTagFilters, tagsDictionary, tagsOptions } =
    useAnalystPresenceFilters();

  return (
    <Stack px={2} pt={3} pb={3} spacing={2}>
      <TwoColumnGrid>
        {/* Status filter */}
        <Autocomplete
          size="small"
          options={STATUS_OPTIONS}
          value={activeStatusFilter}
          onChange={(_, value) => setStatusFilter(value ?? 'all')}
          getOptionLabel={option => t(`tsxAnalystPresence.common.${option}`)}
          disableClearable
          renderInput={params => <TextField {...params} label={t('tsxAnalystPresence.common.availability')} />}
          PaperComponent={props => <Paper {...props} elevation={PAPER_ELEVATION} />}
        />

        {/* Portfolio filter */}
        <Autocomplete
          multiple
          size="small"
          options={tagsDictionary?.portfolio.map(item => item.value) ?? []}
          value={activeTagFilters.portfolio}
          getOptionLabel={option => tagsOptions[option] || option}
          onChange={(_, value) => setTagFilters('portfolio', value)}
          renderInput={params => <TextField {...params} label={t(TAG_LABELS.portfolio)} />}
          PaperComponent={props => <Paper {...props} elevation={PAPER_ELEVATION} />}
        />
      </TwoColumnGrid>

      <TwoColumnGrid>
        {/* Product filter */}
        <Autocomplete
          multiple
          size="small"
          options={tagsDictionary?.products.map(item => item.value) ?? []}
          getOptionLabel={option => tagsOptions[option] || option}
          value={activeTagFilters.products}
          onChange={(_, value) => setTagFilters('products', value)}
          renderInput={params => <TextField {...params} label={t(TAG_LABELS.products)} />}
          PaperComponent={props => <Paper {...props} elevation={PAPER_ELEVATION} />}
        />

        {/* Discipline filter */}
        <Autocomplete
          multiple
          size="small"
          options={tagsDictionary?.primary_disciplines.map(item => item.value) ?? []}
          getOptionLabel={option => tagsOptions[option] || option}
          value={activeTagFilters.primary_disciplines}
          onChange={(_, value) => setTagFilters('primary_disciplines', value)}
          renderInput={params => <TextField {...params} label={t(TAG_LABELS.primary_disciplines)} />}
          PaperComponent={props => <Paper {...props} elevation={PAPER_ELEVATION} />}
        />
      </TwoColumnGrid>
    </Stack>
  );
};
