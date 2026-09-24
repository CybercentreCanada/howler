import { Icon } from '@iconify/react';
import { ContentCopy, KeyboardArrowDown } from '@mui/icons-material';
import {
  Button,
  Card,
  CardActions,
  CardContent,
  Checkbox,
  ClickAwayListener,
  Collapse,
  Divider,
  FormControlLabel,
  IconButton,
  Paper,
  Popper,
  Skeleton,
  Stack,
  Typography,
  useTheme
} from '@mui/material';
import PluginTypography from 'components/elements/PluginTypography';
import useMySnackbar from 'components/hooks/useMySnackbar';
import { get, isEmpty, uniq } from 'lodash-es';
import type { Event } from 'models/entities/generated/Event';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const CaseAggregate: FC<{
  icon?: string;
  iconColor?: string;
  field?: string;
  records?: Partial<Hit | Event>[];
  title?: string;
  subtitle?: string;
}> = ({ icon, iconColor, field, records, title, subtitle }) => {
  const { t } = useTranslation();
  const { showErrorMessage, showSuccessMessage } = useMySnackbar();
  const theme = useTheme();
  const [open, setOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<HTMLDivElement | null>(null);
  const [selection, setSelection] = useState<{ key: string; values: string[] }>({ key: '', values: [] });

  const values = useMemo(
    () =>
      records
        ? uniq(
            records
              .map(_record => get(_record, field!))
              .flat()
              .filter(Boolean)
          )
        : [],
    [field, records]
  );
  const valueStrings = useMemo(() => values.map(String), [values]);
  const valueKey = JSON.stringify(valueStrings);
  const selectedValues = selection.key === valueKey ? selection.values : valueStrings;

  useEffect(() => {
    if (!open) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open]);

  if (!title && (!records || !field)) {
    return <Skeleton height={120} />;
  }

  const canShowValues = !isEmpty(values) && !!field;
  const selectedValueCount = selectedValues.length;
  const allValuesSelected = canShowValues && selectedValueCount === valueStrings.length;
  const copiedValues = valueStrings.filter(value => selectedValues.includes(value)).join(', ');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(copiedValues);
      showSuccessMessage(`${subtitle} ${t('clipboard.success')}`);
    } catch {
      showErrorMessage(`${subtitle} ${t('clipboard.failure')}`);
    }
  };

  return (
    <>
      <Card
        ref={setAnchorEl}
        sx={[
          {
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            transition: theme.transitions.create(['border-bottom-left-radius', 'border-bottom-right-radius'])
          },
          open && {
            borderBottomLeftRadius: '0 !important',
            borderBottomRightRadius: '0 !important'
          }
        ]}
      >
        <CardContent>
          <Stack alignItems="center" spacing={1}>
            <Stack direction="row" alignItems="center" spacing={1}>
              {icon && <Icon fontSize="96px" icon={icon} color={iconColor || theme.palette.grey[700]} />}
              <Typography variant="h3">
                {values.length}
                {!isEmpty(values) && !!title && ' - '}
                {title}
              </Typography>
            </Stack>
            <Typography color="textSecondary">{subtitle}</Typography>
          </Stack>
        </CardContent>
        {canShowValues && (
          <CardActions sx={{ justifyContent: 'center', mt: 'auto', pt: 0 }}>
            <IconButton
              size="small"
              aria-label={`${t('page.cases.dashboard.show_values')}: ${subtitle}`}
              aria-haspopup="dialog"
              aria-expanded={open}
              onClick={() => setOpen(currentOpen => !currentOpen)}
              color={open ? 'primary' : 'default'}
            >
              <KeyboardArrowDown />
            </IconButton>
          </CardActions>
        )}
      </Card>
      <Popper
        open={!!anchorEl && canShowValues}
        anchorEl={anchorEl}
        placement="bottom-start"
        sx={{ zIndex: 1300, maxWidth: '90vw', minWidth: anchorEl?.clientWidth ?? 0 }}
      >
        <Collapse in={open} unmountOnExit>
          <ClickAwayListener onClickAway={() => setOpen(false)}>
            <Paper
              role="dialog"
              aria-label={subtitle}
              sx={{
                minWidth: 240,
                maxWidth: 480,
                p: 1.5,
                borderTopLeftRadius: 0,
                borderTopRightRadius: 0
              }}
            >
              <Stack spacing={1.5}>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={allValuesSelected}
                      indeterminate={selectedValueCount > 0 && !allValuesSelected}
                      onChange={(_event, checked) =>
                        setSelection({ key: valueKey, values: checked ? valueStrings : [] })
                      }
                    />
                  }
                  label={t('page.cases.dashboard.select_all')}
                />
                <Divider />
                <Stack spacing={0.5} sx={{ maxHeight: 240, overflowY: 'auto' }}>
                  {valueStrings.map(value => (
                    <FormControlLabel
                      key={value}
                      control={
                        <Checkbox
                          checked={selectedValues.includes(value)}
                          onChange={(_event, checked) => {
                            setSelection({
                              key: valueKey,
                              values: checked
                                ? [...selectedValues, value]
                                : selectedValues.filter(selectedValue => selectedValue !== value)
                            });
                          }}
                        />
                      }
                      label={
                        <PluginTypography
                          context="caseaggregate"
                          field={field}
                          value={value}
                          sx={{ overflowWrap: 'anywhere' }}
                        >
                          {value}
                        </PluginTypography>
                      }
                    />
                  ))}
                </Stack>
                <Button
                  variant="outlined"
                  startIcon={<ContentCopy />}
                  disabled={selectedValueCount === 0}
                  onClick={() => void handleCopy()}
                >
                  {t('button.copy')}
                </Button>
              </Stack>
            </Paper>
          </ClickAwayListener>
        </Collapse>
      </Popper>
    </>
  );
};

export default memo(CaseAggregate);
