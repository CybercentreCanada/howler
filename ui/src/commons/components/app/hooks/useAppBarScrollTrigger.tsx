import { useScrollTrigger } from '@mui/material';

export function useAppBarScrollTrigger() {
  return useScrollTrigger({
    disableHysteresis: true,
    threshold: 0
  });
}
