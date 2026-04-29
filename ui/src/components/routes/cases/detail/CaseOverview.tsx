import { Clear, Edit, Save } from '@mui/icons-material';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Divider,
  IconButton,
  LinearProgress,
  Skeleton,
  Stack,
  useTheme
} from '@mui/material';
import Markdown from 'components/elements/display/Markdown';
import MarkdownEditor from 'components/elements/MarkdownEditor';
import type { Case } from 'models/entities/generated/Case';
import { useEffect, useState, type FC } from 'react';

const CaseOverview: FC<{ case: Case; updateCase: (_case: Partial<Case>) => Promise<void> }> = ({
  case: _case,
  updateCase
}) => {
  const theme = useTheme();

  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState(_case?.overview);

  useEffect(() => {
    if (!editing && _case?.overview) {
      setOverview(_case.overview);
    }
  }, [_case?.overview, editing]);

  if (!_case) {
    return <Skeleton height={370} />;
  }

  return (
    <Card>
      <CardHeader title={_case.title} subheader={_case.summary} />
      <Stack>
        <Divider />
        <LinearProgress sx={{ opacity: +loading }} />
      </Stack>
      <CardContent sx={{ position: 'relative' }}>
        <Stack direction="row" spacing={1}>
          <Box
            flex={1}
            sx={{
              '& > :first-child': {
                marginTop: '0 !important'
              },
              '& > h1,h2,h3,h4,h5': {
                fontSize: theme.typography.h5.fontSize
              }
            }}
          >
            {editing ? (
              <MarkdownEditor height="40vh" content={overview} setContent={_content => setOverview(_content)} />
            ) : (
              <Markdown md={_case.overview} />
            )}
          </Box>

          <Stack spacing={1}>
            <IconButton
              size="small"
              disabled={loading}
              onClick={async () => {
                if (editing) {
                  try {
                    setLoading(true);
                    await updateCase({ overview });
                  } finally {
                    setEditing(false);
                    setLoading(false);
                  }
                } else {
                  setEditing(true);
                }
              }}
            >
              {editing ? <Save color={loading ? 'disabled' : 'success'} fontSize="small" /> : <Edit fontSize="small" />}
            </IconButton>
            {editing && (
              <IconButton size="small" disabled={loading} onClick={() => setEditing(false)}>
                <Clear color={loading ? 'disabled' : 'error'} fontSize="small" />
              </IconButton>
            )}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default CaseOverview;
