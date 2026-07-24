import ConfirmDeleteModal from 'components/elements/display/modals/ConfirmDeleteModal';
import type { FC, PropsWithChildren, ReactNode } from 'react';
import { createContext, useCallback, useEffect, useState } from 'react';
import { missingContext } from './contextUtils';

export interface ModalOptions {
  disableClose?: boolean;
  height?: number | string | null;
  maxWidth?: string;
  maxHeight?: string;
}

const defaultOptions: ModalOptions = {
  disableClose: false
};

interface ModalContextType {
  showModal: (children: ReactNode, options?: ModalOptions) => () => void;
  withConfirmDeleteModal: (onConfirm: () => void, preferDelete?: boolean, preferCancel?: boolean) => () => void;
  content?: ReactNode;
  setContent: (children: ReactNode) => void;
  options?: ModalOptions;
  close: () => void;
}

const DEFAULT_MODAL_CONTEXT: ModalContextType = {
  showModal: () => missingContext('ModalContext'),
  withConfirmDeleteModal: () => missingContext('ModalContext'),
  setContent: () => missingContext('ModalContext'),
  close: () => missingContext('ModalContext')
};

export const ModalContext = createContext<ModalContextType>(DEFAULT_MODAL_CONTEXT);

const ModalProvider: FC<PropsWithChildren> = ({ children }) => {
  const [content, setContent] = useState<ReactNode>(null);
  const [options, setOptions] = useState<ModalOptions>(defaultOptions);

  useEffect(() => {
    if (!content) {
      setOptions(defaultOptions);
    }
  }, [content]);

  const showModal = useCallback(
    (_children: ReactNode, newOptions?: ModalOptions) => {
      setContent(_children);

      if (options) {
        setOptions({
          ...options,
          ...newOptions
        });
      }

      return () => setContent(null);
    },
    [options]
  );

  const close = useCallback(() => setContent(null), []);

  const withConfirmDeleteModal = useCallback(
    (onConfirm: () => void, preferDelete?: boolean, preferCancel?: boolean) => {
      return showModal(
        <ConfirmDeleteModal onConfirm={onConfirm} preferDelete={preferDelete} preferCancel={preferCancel} />
      );
    },
    [showModal]
  );

  return (
    <ModalContext.Provider value={{ showModal, withConfirmDeleteModal, content, setContent, options, close }}>
      {children}
    </ModalContext.Provider>
  );
};

export default ModalProvider;
