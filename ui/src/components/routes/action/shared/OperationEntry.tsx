import { Delete } from '@mui/icons-material';
import type { SelectChangeEvent } from '@mui/material';
import {
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  IconButton,
  ListItemText,
  MenuItem,
  Select,
  Stack
} from '@mui/material';
import Markdown from 'components/elements/display/Markdown';
import type { ActionOperation } from 'models/ActionTypes';
import type { Operation } from 'models/entities/generated/Operation';
import type { FC } from 'react';
import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { checkArgsAreFilled, operationReady } from 'utils/actionUtils';
import OperationStep from './OperationStep';

const OperationEntry: FC<{
  query: string;
  operation: ActionOperation;
  readonly?: boolean;
  values?: string;
  operations: ActionOperation[];
  onChange?: (operation: Operation) => void;
  onDelete?: () => void;
}> = ({ operation, operations, onChange, onDelete, query, readonly = false, values }) => {
  const { t } = useTranslation();

  const ready = useMemo(() => operationReady(values, operation), [operation, values]);

  const handleChange = useCallback(
    (e: SelectChangeEvent<string>) => {
      if (onChange) {
        onChange({
          operation_id: e.target.value,
          data_json: '{}'
        });
      }
    },
    [onChange]
  );

  return operation?.id ? (
    <Card variant="outlined" key={operation?.id} sx={[!readonly && ready && { borderColor: 'success.main' }]}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="start" spacing={1}>
            <Stack spacing={1}>
              <Select
                value={operation?.id}
                size="small"
                disabled={readonly || operations.length < 2}
                onChange={handleChange}
              >
                {operations
                  .sort((a, b) => (b.priority ?? -1) - (a.priority ?? -1))
                  .map(_operation => (
                    <MenuItem key={_operation?.id} value={_operation?.id}>
                      <ListItemText
                        primary={t(_operation.i18nKey) ?? _operation.title}
                        secondary={_operation.description?.short}
                      />
                    </MenuItem>
                  ))}
              </Select>
              {operation.triggers.map(_trigger => (
                <Chip
                  key={_trigger}
                  size="small"
                  label={t(`route.actions.trigger.${_trigger}`)}
                  sx={{ alignSelf: 'start' }}
                />
              ))}
            </Stack>
            <Divider flexItem orientation="vertical" />
            <Box flex={1} sx={{ '& pre': { whiteSpace: 'normal' } }}>
              <Markdown md={operation.description?.long} />
            </Box>
            {!readonly && (
              <>
                <Divider flexItem orientation="vertical" />

                <IconButton onClick={onDelete}>
                  <Delete />
                </IconButton>
              </>
            )}
          </Stack>
          <Divider orientation="horizontal" />
          {operation.steps
            .filter((_, index, arr) => (index > 0 ? checkArgsAreFilled(arr[index - 1], values) : true))
            .map(step => {
              return (
                <OperationStep
                  readonly={readonly}
                  key={Object.keys(step.args).join('')}
                  step={step}
                  query={query}
                  values={values}
                  setValues={_values =>
                    onChange({
                      operation_id: operation?.id,
                      data_json: _values
                    })
                  }
                />
              );
            })}
        </Stack>
      </CardContent>
    </Card>
  ) : null;
};

export default OperationEntry;
