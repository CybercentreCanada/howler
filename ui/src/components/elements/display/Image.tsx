import { Close } from '@mui/icons-material';
import { Box, IconButton, lighten, Modal } from '@mui/material';
import { useState, type DetailedHTMLProps, type FC, type ImgHTMLAttributes } from 'react';

const Image: FC<DetailedHTMLProps<ImgHTMLAttributes<HTMLImageElement>, HTMLImageElement>> = props => {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <img {...props} style={{ ...(props.style ?? {}), cursor: 'pointer' }} onClick={() => setShowModal(true)} />
      <Modal open={showModal} onClose={() => setShowModal(false)}>
        <Box
          sx={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
          onClick={() => setShowModal(false)}
        >
          <IconButton
            onClick={() => setShowModal(false)}
            sx={theme => ({
              position: 'fixed',
              top: '2rem',
              right: '2rem',
              backgroundColor: 'background.paper',
              '&:hover': {
                backgroundColor: lighten(theme.palette.background.paper, 0.1)
              }
            })}
          >
            <Close />
          </IconButton>
          <img {...props} style={{ ...(props.style ?? {}), maxWidth: '70vw', maxHeight: '70vh' }} />
        </Box>
      </Modal>
    </>
  );
};

export default Image;
