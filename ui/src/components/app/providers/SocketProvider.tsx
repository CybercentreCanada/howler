/* eslint-disable no-console */
import api from 'api';
import useMyLocalStorage from 'components/hooks/useMyLocalStorage';
import type { PropsWithChildren } from 'react';
import { createContext, useCallback, useEffect, useRef, useState } from 'react';
import { StorageKey } from 'utils/constants';
import { getStored, setAxiosCache, setStored } from 'utils/sessionStorage';
import { isHitUpdate } from 'utils/socketUtils';

export type ListenerType<K extends keyof WebSocketEventMap> = (this: WebSocket, ev: WebSocketEventMap[K]) => void;

/**
 * The type of the data returned from the server during a WebSocket connection.
 * The only guaranteed keys are error, message and status.
 */
export type RecievedDataType<T = { [index: string]: any }> = T & {
  error: boolean;
  message: string;
  type: string;
  status: number;
};

/**
 * Enum to help track the status of the Websocket, since the corresponding websocket enums are directly on the object
 */
export enum Status {
  CLOSED = WebSocket.CLOSED,
  CLOSING = WebSocket.CLOSING,
  CONNECTING = WebSocket.CONNECTING,
  OPEN = WebSocket.OPEN
}

interface SocketContextType {
  /**
   * Add a listener for events from the websocket connection.
   * @param key The unique key used to track this listener
   * @param v The listener function
   */
  addListener: <T = { [index: string]: any }>(key: string, v: (data: RecievedDataType<T>) => void) => void;

  /**
   * Remove a listener from the websocket connection.
   * @param key The unique key used to track the listener we're removing
   */
  removeListener: (key: string) => void;

  /**
   * Wrapper function for WebSocket.send(...). Used to send data to the server.
   */
  emit: (data: any) => void;

  /**
   * The status of the websocket connection.
   */
  status: Status;

  /**
   * Manually attempt reconnecting to the server.
   */
  reconnect: () => void;

  /**
   * Helper function to tell if the socket is open
   */
  isOpen: () => boolean;
}

export const SocketContext = createContext<SocketContextType>(null);

const SocketProvider: React.FC<PropsWithChildren> = ({ children }) => {
  const { get } = useMyLocalStorage();

  // In order to persist the connection through state changes, we use a ref
  const socket = useRef<WebSocket>();

  // Due to react setState race conditions, listeners are also stored in a ref
  const listeners = useRef<{ [index: string]: ListenerType<'message'> }>({});

  // We will need to use the app token to authenticate.
  // Note the token MUST BE either an app token or a JWT - user/pass or apikey authentication isn't allowed
  const appToken = get<string>(StorageKey.APP_TOKEN);

  const [status, setStatus] = useState<Status>(Status.CLOSED);
  // Track whether we should retry the connection to the server
  const [retry, setRetry] = useState(true);
  // Track the number of failed attempts when connecting to the server
  const [failedAttempts, setFailedAttempts] = useState(0);

  const onClose: ListenerType<'close'> = useCallback(
    e => {
      // https://www.rfc-editor.org/rfc/rfc6455:
      // 1006 is a reserved value and MUST NOT be set as a status code in a
      // Close control frame by an endpoint.  It is designated for use in
      // applications expecting a status code to indicate that the
      // connection was closed abnormally, e.g., without sending or
      // receiving a Close control frame.
      if (e.code === 1006) {
        setTimeout(() => setRetry(true), 1000 * Math.pow(2, failedAttempts));
        setFailedAttempts(failedAttempts + 1);
      }
      // https://www.rfc-editor.org/rfc/rfc6455:
      // 1008 indicates that an endpoint is terminating the connection
      // because it has received a message that violates its policy.  This
      // is a generic status code that can be returned when there is no
      // other more suitable status code (e.g., 1003 or 1009) or if there
      // is a need to hide specific details about the policy.
      //
      // In our case, we use 1008 to indicate the connection did something wrong.
      // For more granular error handling, we provide a status code equivalent
      // To the HTTP status codes we know (400, 401, 403, etc.).
      else if (e.code === 1008) {
        try {
          // Check to see if there's any data we can parse, or if it's just a bad connection
          const data: RecievedDataType = JSON.parse(e.reason);

          // If we are unauthorized, we can update the token through the usual process and tell
          // the connection to retry with the new token
          if (data.status === 401) {
            api.user.whoami.get().then(() => setRetry(true));
          } else {
            console.error(data);
            setRetry(false);
          }
        } catch (err) {
          // There's no useful data, or the refresh attempt failed.
          // Either way, we can't really do anything
        }
      }

      setStatus(Status.CLOSED);
    },
    [failedAttempts]
  );

  /**
   * Handler for errors with the websocket connection
   */
  const onWsError: ListenerType<'error'> = useCallback(() => {
    setStatus(Status.CLOSING);
    socket.current?.close();
    setStatus(Status.CLOSED);

    // Exponential fall off of connection attempts (1s, then 2, 4, 8, 16, etc.)
    setTimeout(() => setRetry(true), 1000 * Math.pow(2, failedAttempts));
    setFailedAttempts(failedAttempts + 1);
  }, [failedAttempts]);

  /**
   * Handler for messages sent form the server NOT RELATED to the websocket connection itself
   *
   * i.e. We sent bad data, did something the server didn't like, etc.
   */
  const onMessageError: ListenerType<'message'> = useCallback(e => {
    try {
      const data: RecievedDataType = JSON.parse(e.data);

      if (data?.error || data?.status >= 400) {
        console.warn(data?.message || 'Websocket Error');
      }
    } catch (err) {
      console.warn('Websocket Error');
    }
  }, []);

  /**
   * Handler called when the page unloads, used to gracefully close the socket.
   *
   * This isn't a hard requirement to run, but it's good form.
   */
  const onBeforeUnload = useCallback(() => socket.current?.close(), []);

  // Effect used to start a connection to the websocket server
  useEffect(() => {
    // If the socket is already open, ovbviously we don't need to connect again
    if ([Status.OPEN, Status.CONNECTING].includes(status)) {
      if (status === Status.OPEN) {
        setRetry(false);
      }

      return;
    }

    // If we aren't retrying or we don't have an app token we can use, we don't continue
    if (!retry || !appToken) return;

    setRetry(false);

    // Here we go!
    setStatus(Status.CONNECTING);

    const host = window.location.host.startsWith('localhost') ? 'localhost:5000' : window.location.host;
    const protocol = window.location.protocol.startsWith('http:') ? 'ws' : 'wss';
    const ws = new WebSocket(`${protocol}://${host}/socket/v1/connect`);

    // Add our listeners to the websocket
    ws.addEventListener('close', onClose);
    ws.addEventListener('error', onWsError);
    ws.addEventListener('message', onMessageError);

    ws.addEventListener('open', () => {
      socket.current = ws;

      // Hooray! The connection was successful.
      // But we aren't done yet - we need to authenticate before doing anything else.
      // So, we send the token
      ws.send(appToken);

      // Just for this first response, we add a custom listener to the socket.
      // It waits for a response from our token message, and ensures the server accepted it
      const onAuth: ListenerType<'message'> = e => {
        ws.removeEventListener('message', onAuth);

        const data: RecievedDataType = JSON.parse(e.data);

        // If there's no error, the token was accepted and we're good to go!
        if (!data.error) {
          console.debug(data.message);
          setStatus(Status.OPEN);
          setRetry(false);
          setFailedAttempts(0);

          // If there is, the server will close the socket and the token refreshing code will take over
        } else {
          console.error(data.message);
        }
      };

      ws.addEventListener('message', onAuth);
    });

    window.addEventListener('beforeunload', onBeforeUnload);
  }, [appToken, status, onBeforeUnload, onClose, onWsError, onMessageError, retry]);

  // Handler for when the socket opens
  useEffect(() => {
    // The socket is open, so we can add any listeners that were waiting for it to open
    if (status === Status.OPEN) {
      Object.values(listeners.current).forEach(l => {
        socket.current?.removeEventListener('message', l);
        socket.current?.addEventListener('message', l);
      });
    }
  }, [listeners, status]);

  // Handler for when the socket closes
  useEffect(() => {
    if (!socket.current) return;

    if ([Status.CLOSED, Status.CLOSING].includes(status)) {
      socket.current.removeEventListener('close', onClose);
      socket.current.removeEventListener('error', onWsError);
      socket.current.removeEventListener('message', onMessageError);

      Object.values(listeners.current).forEach(l => socket.current.removeEventListener('message', l));
      listeners.current = {};

      window.removeEventListener('beforeunload', onBeforeUnload);

      socket.current.close();
      socket.current = null;
    }
  }, [status, socket, appToken, onBeforeUnload, onClose, onWsError, onMessageError]);

  const addListener: SocketContextType['addListener'] = useCallback((key, callback) => {
    // If a listener with the same key already exists, remove it.
    if (listeners.current[key]) {
      socket.current?.removeEventListener('message', listeners[key]);
    }

    // We wrap the callback so that all the listeners don't need to JSON.parse the data
    const wrapped: ListenerType<'message'> = ev => {
      const parsedData = JSON.parse(ev.data) as RecievedDataType;

      if (isHitUpdate(parsedData) && parsedData.status < 300) {
        setStored(StorageKey.ETAG, {
          ...getStored(StorageKey.ETAG),
          [parsedData.hit.howler.id]: parsedData.version
        });

        setAxiosCache(parsedData.version, {
          api_response: parsedData.hit,
          api_error_message: '',
          api_server_version: '',
          api_status_code: parsedData.status
        });
      }

      callback(parsedData as RecievedDataType<any>);
    };

    socket.current?.addEventListener('message', wrapped);

    listeners.current[key] = wrapped;
  }, []);

  const removeListener: SocketContextType['removeListener'] = useCallback((key: string) => {
    socket.current?.removeEventListener('message', listeners.current[key]);

    delete listeners.current[key];
  }, []);

  const emit: SocketContextType['emit'] = useCallback(
    data => {
      if (typeof data !== 'string') {
        data = JSON.stringify(data);
      }

      if (status !== Status.OPEN || !socket.current) {
        console.warn('socket closed, not sending');
        return;
      }

      socket.current?.send(data);
    },
    [status]
  );

  const isOpen = useCallback(() => status === Status.OPEN, [status]);

  const reconnect: SocketContextType['reconnect'] = useCallback(() => setRetry(true), []);

  return (
    <SocketContext.Provider value={{ addListener, removeListener, emit, status, reconnect, isOpen }}>
      {children}
    </SocketContext.Provider>
  );
};

export default SocketProvider;
