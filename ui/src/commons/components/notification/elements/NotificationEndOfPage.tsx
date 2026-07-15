import { NotificationSkeleton } from 'commons/components/notification/elements/NotificationSkeleton';
import { memo, useEffect, useRef, useState, type FC, type RefObject } from 'react';

function useOnScreen(ref: RefObject<Element>, rootMargin = '0px') {
  // State and setter for storing whether element is visible
  const [isIntersecting, setIntersecting] = useState(false);
  useEffect(() => {
    const observerRef = ref.current;
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Update our state when observer callback fires
        setIntersecting(entry.isIntersecting);
      },
      {
        rootMargin
      }
    );
    if (observerRef) {
      observer.observe(observerRef);
    }
    return () => {
      if (observerRef) {
        observer.unobserve(observerRef);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty array ensures that effect is only run on mount and unmount
  return isIntersecting;
}

export const NotificationEndOfPage: FC<{ endOfPage?: boolean; onLoading?: () => void }> = memo(
  ({ endOfPage = true, onLoading = () => null }) => {
    const ref = useRef();
    const onScreen = useOnScreen(ref);

    useEffect(() => {
      if (onScreen) {
        onLoading();
      }
    }, [onLoading, onScreen]);

    return endOfPage ? null : (
      <div ref={ref} style={{ display: 'flex', justifyContent: 'center' }}>
        <NotificationSkeleton />
      </div>
    );
  }
);
