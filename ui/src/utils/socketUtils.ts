import type { RecievedDataType } from 'components/app/providers/SocketProvider';
import type { CaseUpdate } from 'models/socket/CaseUpdate';
import type { HitUpdate } from 'models/socket/HitUpdate';
import type { ViewersUpdate } from 'models/socket/ViewersUpdate';

/**
 * Checks to see if the data recieved from the socket is a hit update
 * @param data The data recieved from the socket
 * @returns whether the data is a hit update
 */
export const isHitUpdate = (data: any): data is RecievedDataType<HitUpdate> => {
  return data.version && data.hit;
};

/**
 * Checks to see if the data received from the socket is a case update
 * @param data The data received from the socket
 * @returns whether the data is a case update
 */
export const isCaseUpdate = (data: any): data is RecievedDataType<CaseUpdate> => {
  return data.type === 'cases' && data.case;
};

/**
 * Checks to see if the data received from the socket is a viewers update
 * @param data The data received from the socket
 * @returns whether the data is a viewers update
 */
export const isViewersUpdate = (data: any): data is RecievedDataType<ViewersUpdate> => {
  return data.type === 'viewers_update' && data.viewers && data.id;
};
