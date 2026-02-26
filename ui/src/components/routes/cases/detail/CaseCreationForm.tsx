
import { AddCircle } from '@mui/icons-material';
import { Button, Typography } from '@mui/material';
import Card from '@mui/material/Card/Card';
import Grid from '@mui/material/Grid/Grid';
import TextField from '@mui/material/TextField/TextField';
import MarkdownEditor from 'components/elements/MarkdownEditor';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import { useState, type FC } from 'react';
import { useTranslation } from 'react-i18next';

const CreateCase: FC<{
  targetHit: Hit;
  onCreate: (newCase: Partial<Case>) => Promise<void>;
}> = ({ targetHit, onCreate }) => {
  const [loading, setLoading] = useState(false);
  const [_case, setCase] = useState<Partial<Case>>({ title: '', summary: '', overview: '', items: [ { id: targetHit.howler.id, type: 'hit', path: '', value: targetHit.howler.id }] });
  const { t } = useTranslation();



  const dirty = _case.title !== '' && _case.summary !== '';

  const onSubmit = async () => {
    if (dirty) {
      setLoading(true);
      await onCreate(_case);
      setLoading(false);
    }
  };

  return (


    <Card key="new_case" sx={{ p: 0, position: 'relative', maxHeight: '80vh'}}>
      <Grid container spacing={2}>
        <Grid item xs={12} sx={{ mt: 2, mx: 2 }}>
          <Typography variant="h6">Create new case</Typography>
        </Grid>
        <Grid item xs={12} sx={{ mx: 2 }}>
          <TextField required id="outlined-basic" label="Title" variant="outlined" sx={{ width: '100%' }} onChange={(e) => setCase(c => ({...c, title: e.target.value}))} />
        </Grid>
        <Grid item xs={12} sx={{ mx: 2 }}>
          <TextField required id="outlined-basic" label="Summary" variant="outlined"  sx={{ width: '100%' }} onChange={(e) => setCase(c => ({...c, summary: e.target.value}))} />
        </Grid>
        <Grid item xs={12} sx={{ mt: 2, maxHeight: '400px', minHeight: '200px', overflowY: 'hidden' }}>
          <Typography variant="h6" sx={{mx: 2, fontSize: '1rem' }}>Overview</Typography>
          <MarkdownEditor height="100%" content={_case.overview} setContent={(overview) => setCase(c => ({ ...c, overview }))} />
        </Grid>
        <Grid item xs={8}>

        </Grid>
        <Grid item xs={4} >
          <Button variant="contained" sx={{ mx: 2, mb: 2 }} disabled={loading || !dirty} onClick={() => {
            onSubmit();
          }}>
          <AddCircle sx={{ mr: 1 }}/>
            {t('route.cases.create')}
          </Button>
        </Grid>
      </Grid>

    </Card>
  )
};

export default CreateCase;
