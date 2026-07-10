import { Warning as WarningIcon } from '@mui/icons-material';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';

export const UpdateErrorMessage = ({ message }: { message: string }) => {
  return (
    <Box
      sx={{
        mt: 3,
        backgroundColor: theme => alpha(theme.palette.error.main, 0.125),
        border: theme => `1px solid ${alpha(theme.palette.error.main, 0.25)}`,
        borderRadius: 1
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5 }}>
        <WarningIcon color="error" fontSize="small" />
        <Typography color="error" variant="body2">
          {message}
        </Typography>
      </Box>
    </Box>
  );
};
