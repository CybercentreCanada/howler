import Circle from '@mui/icons-material/Circle';
import { alpha, Stack } from '@mui/material';

const TypingIndicator = () => {
  return (
    <Stack
      direction="row"
      sx={theme => ({
        ml: 1,
        p: 1,
        height: '20px',
        borderRadius: theme.shape.borderRadius,
        backgroundColor: alpha('rgb(128, 128, 128)', 0.25),
        '@keyframes bounce': {
          '0%, 60%, 100%': { transform: 'translateY(0)' },
          '30%': { transform: 'translateY(-6px)' }
        },
        '& > svg': {
          fontSize: '6px',
          animation: 'bounce 750ms infinite ease-in-out',
          marginBottom: '-4px',
          opacity: 0.75,
          '&:nth-of-type(2)': {
            animationDelay: '100ms'
          },
          '&:nth-of-type(3)': {
            animationDelay: '200ms'
          }
        }
      })}
      display="flex"
      alignItems="center"
    >
      <Circle />
      <Circle />
      <Circle />
    </Stack>
  );
};

export default TypingIndicator;
