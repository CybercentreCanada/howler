import { Refresh } from '@mui/icons-material';
import { Box, CircularProgress, IconButton, Tooltip } from '@mui/material';
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Imperative handle exposed to the parent via ref.
 * The parent calls `handleRefreshComplete` once each refreshable panel finishes its data fetch,
 * allowing ViewRefresh to track how many panels are still in flight.
 */
export interface ViewRefreshHandle {
  handleRefreshComplete: (panelId: string, refreshTick: symbol) => void;
  updateViewCardIds: (viewCardIds: string[]) => void;
  updateRefreshRate: () => void;
}

interface ViewRefreshProps {
  /** Stable refs let the AppBar-registered node read current Home dashboard values. */
  refreshRateRef: { current: number };
  viewCardIdsRef: { current: string[] };
  /** Called when a refresh cycle begins. Should update `refreshTick` in the parent to signal panels. */
  onRefresh: (refreshTick: symbol) => void;
}

/**
 * Self-contained refresh control that owns the countdown timer and refreshing state.
 * Isolating this state here prevents the progress ticker (which fires every `refreshRate * 10`ms)
 * from causing unnecessary re-renders in the parent Home component.
 */
const ViewRefresh = forwardRef<ViewRefreshHandle, ViewRefreshProps>(
  ({ refreshRateRef, viewCardIdsRef, onRefresh }, ref) => {
    const { t } = useTranslation();

    const [progress, setProgress] = useState(0);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [refreshRateVersion, setRefreshRateVersion] = useState(0);
    const pendingRefreshes = useRef(new Set<string>());
    const registeredCardIds = useRef(new Set<string>());
    const activeRefreshTick = useRef<symbol | undefined>(undefined);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
      registeredCardIds.current = new Set(viewCardIdsRef.current);
    }, [viewCardIdsRef]);

    /**
     * Called by the parent (via ref) when a refreshable dashboard panel finishes fetching.
     * Clears the refreshing state once all pending panels have reported back.
     */
    const handleRefreshComplete = useCallback((panelId: string, refreshTick: symbol) => {
      if (refreshTick !== activeRefreshTick.current || !pendingRefreshes.current.delete(panelId)) {
        return;
      }

      if (pendingRefreshes.current.size === 0) {
        activeRefreshTick.current = undefined;
        setIsRefreshing(false);
        setProgress(0);
      }
    }, []);

    const updateViewCardIds = useCallback((viewCardIds: string[]) => {
      const nextCardIds = new Set(viewCardIds);

      if (activeRefreshTick.current) {
        for (const pendingPanelId of pendingRefreshes.current) {
          if (!nextCardIds.has(pendingPanelId)) {
            pendingRefreshes.current.delete(pendingPanelId);
          }
        }

        for (const panelId of nextCardIds) {
          if (!registeredCardIds.current.has(panelId)) {
            pendingRefreshes.current.add(panelId);
          }
        }

        if (pendingRefreshes.current.size === 0) {
          activeRefreshTick.current = undefined;
          setIsRefreshing(false);
          setProgress(0);
        }
      }

      registeredCardIds.current = nextCardIds;
    }, []);

    const updateRefreshRate = useCallback(() => {
      setRefreshRateVersion(version => version + 1);
    }, []);

    // Expose completion and synchronization methods without leaking the rest of the component's state.
    useImperativeHandle(ref, () => ({ handleRefreshComplete, updateViewCardIds, updateRefreshRate }), [
      handleRefreshComplete,
      updateRefreshRate,
      updateViewCardIds
    ]);

    const triggerRefresh = useCallback(() => {
      const refreshTick = Symbol();
      const viewCardIds = viewCardIdsRef.current;
      setIsRefreshing(true);
      activeRefreshTick.current = refreshTick;
      pendingRefreshes.current = new Set(viewCardIds);
      registeredCardIds.current = new Set(viewCardIds);

      if (viewCardIds.length === 0) {
        activeRefreshTick.current = undefined;
        setIsRefreshing(false);
        setProgress(0);
        return;
      }

      onRefresh(refreshTick);
    }, [onRefresh, viewCardIdsRef]);

    useEffect(() => {
      if (isRefreshing) return;

      timerRef.current = setTimeout(() => {
        if (progress >= 99) {
          triggerRefresh();
        } else {
          setProgress(currentProgress => currentProgress + 1);
        }
      }, refreshRateRef.current * 10);

      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
      };
    }, [progress, isRefreshing, refreshRateRef, refreshRateVersion, triggerRefresh]);

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
