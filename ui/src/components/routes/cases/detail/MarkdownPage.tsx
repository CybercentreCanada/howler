import { Cancel, Edit, Save } from '@mui/icons-material';
import { Box, Divider, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import ThemedEditor from 'components/elements/ThemedEditor';
import ClassificationChip from 'components/elements/display/ClassificationChip';
import Markdown from 'components/elements/display/Markdown';
import type { Case } from 'models/entities/generated/Case';
import type { Item } from 'models/entities/generated/Item';
import { useCallback, useEffect, useMemo, useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import useCase from '../hooks/useCase';
import { buildPathFromID } from '../utils';

const MarkdownPage: FC<{ case: Case; item: Item }> = ({ case: _case, item }) => {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [markdown, setMarkdown] = useState(item.value ?? '');
  const [saving, setSaving] = useState(false);

  const { update } = useCase({ case: _case });

  useEffect(() => {
    setMarkdown(item.value ?? '');
    setIsEditing(false);
  }, [item.id, item.value]);

  const path = useMemo(() => buildPathFromID(_case, item.parent), [_case, item.parent]);

  const handleCancel = useCallback(() => {
    setMarkdown(item.value ?? '');
    setIsEditing(false);
  }, [item.value]);

  const handleSave = useCallback(async () => {
    if (!_case.case_id || !item.id) {
      return;
    }

    const nextItems = (_case.items ?? []).map(_item => {
      if (_item.id === item.id) {
        return {
          ..._item,
          value: markdown
        };
      }

      return _item;
    });

    try {
      setSaving(true);
      await update({ items: nextItems });
      setIsEditing(false);
    } finally {
      setSaving(false);
    }
  }, [_case.case_id, _case.items, item.id, markdown, update]);

  return (
    <Box p={1} sx={{ mt: -1, minHeight: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" alignItems="center" spacing={1}>
        <Stack direction="row">
          <Typography variant="h6" color="text.secondary">
            {path}/
          </Typography>
          <Typography variant="h6">{item.name}</Typography>
        </Stack>
        {item.classification && <ClassificationChip classification={item.classification} format="long" />}
        <div style={{ flex: 1 }} />
        {isEditing && (
          <Tooltip title={t('button.save')}>
            <IconButton size="small" color="success" onClick={handleSave} disabled={saving}>
              <Save fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title={isEditing ? t('button.cancel') : t('edit')}>
          <IconButton
            size="small"
            color={isEditing ? 'error' : 'default'}
            onClick={isEditing ? handleCancel : () => setIsEditing(true)}
            disabled={saving}
          >
            {isEditing ? <Cancel fontSize="small" /> : <Edit fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Stack>
      <Divider />
      {isEditing ? (
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} sx={{ mt: 1, flex: 1, minHeight: 0 }}>
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              border: theme => `1px solid ${theme.palette.divider}`,
              borderRadius: 1,
              overflow: 'hidden'
            }}
          >
            <ThemedEditor
              id="markdown-editor"
              language="markdown"
              value={markdown}
              onChange={value => setMarkdown(value ?? '')}
              options={{ wordWrap: 'on', scrollBeyondLastLine: false }}
              height="100%"
            />
          </Box>
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              border: theme => `1px solid ${theme.palette.divider}`,
              borderRadius: 1,
              p: 1,
              overflow: 'auto'
            }}
          >
            <Markdown md={markdown} />
          </Box>
        </Stack>
      ) : (
        <Markdown md={markdown} />
      )}
    </Box>
  );
};

export default MarkdownPage;
