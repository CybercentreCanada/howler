import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Modal from '@mui/material/Modal';
import api from 'api';
import useMyApi from 'components/hooks/useMyApi';
import useMySnackbar from 'components/hooks/useMySnackbar';
import type { Case } from 'models/entities/generated/Case';
import type { Hit } from 'models/entities/generated/Hit';
import { useCallback, useState } from 'react';
import CreateCase from './CaseCreationForm';

const CaseCreationModal = ({ hit }: { hit: Hit }) => {
  const [open, setOpen] = useState(false);
  const handleOpen = () => setOpen(true);
  const handleClose = () => setOpen(false);
  const { dispatchApi } = useMyApi();
  const { showSuccessMessage } = useMySnackbar();

    const createCase = useCallback(
      async (newCase: Partial<Case>) => {
        if (!newCase?.title || !newCase?.summary) {
          return;
        }

        try {
          await dispatchApi(api.v2.case.post(newCase)).then((createdCase) => {
            showSuccessMessage(`Case ${createdCase.title} created successfully!`);
          });
        } finally {
          return;
        }
      },
      [dispatchApi]
    );

  return (<>
  <Button variant="outlined" onClick={handleOpen} sx={{ height: 40, }}>Create case</Button>
  <Modal
    open={open}
    onClose={handleClose}
    aria-labelledby="modal-modal-title"
    aria-describedby="modal-modal-description"
        sx={theme => ({
          mt: 10,
          mx: 'auto',
          maxWidth: '600px',
          maxHeight: '600px',
        })}
  >
    <Box>
      <CreateCase targetHit={hit} onCreate={async (newCase) => {
        await createCase(newCase);
        handleClose();
      }} >
      </CreateCase>
    </Box>
  </Modal></>);
};

export default CaseCreationModal;
