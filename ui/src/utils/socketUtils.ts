import type { RecievedDataType } from 'components/app/providers/SocketProvider';
import type { HitUpdate } from 'models/socket/HitUpdate';

/**
 * Checks to see if the data recieved from the socket is a hit update
 * @param data The data recieved from the socket
 * @returns whether the data is a hit update
 */
export const isHitUpdate = (data: any): data is RecievedDataType<HitUpdate> => {
  return data.version && data.hit;
};
