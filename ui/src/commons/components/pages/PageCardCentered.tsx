import { Card, styled, useMediaQuery, useTheme } from '@mui/material';
import { memo } from 'react';

const StyledCard = styled(Card)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  position: 'absolute',
  left: '50%', // X
  top: '50%', // Y
  transform: 'translate(-50%, -50%)',
  maxWidth: '22rem',
  backgroundColor: theme.palette.background.paper,
  borderRadius: '4px',
  [theme.breakpoints.down('sm')]: {
    backgroundColor: theme.palette.background.default,
    width: '100%',
    maxWidth: '22rem',
    padding: '0rem 1rem 3rem'
  },
  [theme.breakpoints.up('sm')]: {
    width: '22rem',
    padding: '0 2rem 3rem'
  }
}));

function PageCardCentered({ children }) {
  const theme = useTheme();
  const isXs = useMediaQuery(theme.breakpoints.only('xs'));
  return <StyledCard elevation={isXs ? 0 : 4}>{children}</StyledCard>;
}

export default memo(PageCardCentered);
