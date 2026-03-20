import { Refresh } from '@mui/icons-material';
import { Box, CircularProgress, IconButton, Tooltip } from '@mui/material';
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Imperative handle exposed to the parent via ref.
 * The parent calls `handleRefreshComplete` once each ViewCard finishes its data fetch,
 * allowing ViewRefresh to track how many cards are still in flight.
 */
export interface ViewRefreshHandle {
  handleRefreshComplete: () => void;
}

interface ViewRefreshProps {
  /** Auto-refresh interval in seconds (e.g. 15, 30, 60, 300). */
  refreshRate: number;
  /** Number of ViewCards currently on the dashboard. Used to track pending fetches. */
  viewCardCount: number;
  /** Called when a refresh cycle begins. Should update `refreshTick` in the parent to signal ViewCards. */
  onRefresh: () => void;
}

/**
 * Self-contained refresh control that owns the countdown timer and refreshing state.
 * Isolating this state here prevents the progress ticker (which fires every `refreshRate * 10`ms)
 * from causing unnecessary re-renders in the parent Home component.
 */
const ViewRefresh = forwardRef<ViewRefreshHandle, ViewRefreshProps>(
  ({ refreshRate, viewCardCount, onRefresh }, ref) => {
    const { t } = useTranslation();

    const [progress, setProgress] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const pendingRefreshes = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    /**
     * Called by the parent (via ref) each time a ViewCard finishes fetching.
     * Clears the refreshing state once all cards have reported back.
     */
    const handleRefreshComplete = useCallback(() => {
      pendingRefreshes.current -= 1;
      if (pendingRefreshes.current <= 0) {
        setIsRefreshing(false);
        setProgress(0);
      }
    }, []);

    // Expose handleRefreshComplete to the parent without leaking the rest of the component's state.
    useImperativeHandle(ref, () => ({ handleRefreshComplete }), [handleRefreshComplete]);

    const triggerRefresh = useCallback(() => {
      setIsRefreshing(true);
      pendingRefreshes.current = viewCardCount;

      if (viewCardCount === 0) {
        setIsRefreshing(false);
        setProgress(0);
        return;
      }

      onRefresh();
    }, [viewCardCount, onRefresh]);

    useEffect(() => {
      if (isRefreshing) return;

      if (progress >= 100) {
        triggerRefresh();
        return;
      }

      timerRef.current = setTimeout(() => {
        setProgress(prev => prev + 1);
      }, refreshRate * 10);

      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }, [progress, isRefreshing, refreshRate, triggerRefresh]);

    return (
      <Box sx={{ position: 'relative', display: 'inline-flex' }}>
        {isRefreshing ? (
          <CircularProgress variant="indeterminate" size={32} />
        ) : (
          <CircularProgress variant="determinate" value={progress} size={32} />
        )}
        <Box
          sx={{
            top: 0,
            left: 0,
            bottom: 0,
            right: 0,
            position: 'absolute',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <Tooltip title={t('refresh')}>
            <IconButton onClick={triggerRefresh} disabled={isRefreshing} color="primary" size="small">
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    );
  }
);

ViewRefresh.displayName = 'ViewRefresh';

export default ViewRefresh;
