import { closestCorners, DndContext, type DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext } from '@dnd-kit/sortable';
import { Add } from '@mui/icons-material';
import { Button, Stack, Typography } from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import { FieldContext } from 'components/app/providers/FieldProvider';
import Phrase from 'components/elements/addons/search/phrase/Phrase';
import { get, isObject } from 'lodash-es';
import type { Hit } from 'models/entities/generated/Hit';
import { memo, useCallback, useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import TemplateDnD from './TemplateDnD';

const TemplateEditor = ({
  hit,
  fields,
  setFields,
  onRemove,
  onAdd
}: {
  hit: Hit;
  fields: string[];
  setFields: (displayFields: string[]) => void;
  onRemove: (field: string) => void;
  onAdd: (field: string) => void;
}) => {
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);
  const { getHitFields } = useContext(FieldContext);

  const [phrase, setPhrase] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const tryAddField = useCallback(() => {
    if (suggestions.includes(phrase)) {
      if (!fields.includes(phrase)) {
        onAdd(phrase);
        setPhrase('');
      }
    }
  }, [fields, onAdd, phrase, suggestions]);

  const checkForActions = useCallback(
    (e: any) => {
      if (e.isEnter) {
        tryAddField();
      }
    },
    [tryAddField]
  );

  useEffect(() => {
    getHitFields().then(suggestionFields => setSuggestions(suggestionFields.map(f => f.key)));
  }, [getHitFields]);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;

      if (active.id !== over.id) {
        const oldIndex = (fields ?? []).findIndex(entry => entry === active.id);
        const newIndex = (fields ?? []).findIndex(entry => entry === over.id);

        setFields(arrayMove(fields, oldIndex, newIndex));
      }
    },
    [fields, setFields]
  );

  return (
    <Stack spacing={1} width="100%" alignItems="stretch">
      <DndContext collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
        <SortableContext items={(fields ?? []).map(entry => entry)}>
          {fields.map(field => {
            let data = get(hit, field);
            if (!data) {
              data = 'N/A';
            } else if (isObject(data)) {
              data = JSON.stringify(data);
            }

            return (
              <TemplateDnD
                field={field}
                data={data}
                onRemove={onRemove}
                tooltipTitle={(config.indexes.hit[field].description ?? t('none')).split('\n')[0]}
                key={field}
              />
            );
          })}
        </SortableContext>
      </DndContext>

      <Stack direction="row" sx={{ '& > div': { flex: 1 } }} spacing={1}>
        <Phrase
          suggestions={suggestions}
          value={phrase}
          onChange={setPhrase}
          onKeyDown={checkForActions}
          size="small"
        />
        <Button
          variant="outlined"
          size="small"
          sx={{ marginLeft: 'auto' }}
          startIcon={<Add fontSize="small" />}
          disabled={!suggestions.includes(phrase) || fields.includes(phrase)}
          onClick={tryAddField}
        >
          {t('button.add')}
        </Button>
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {t('route.templates.prompt')}
      </Typography>
    </Stack>
  );
};

export default memo(TemplateEditor);
