import type { Hit } from 'models/entities/generated/Hit';

export interface HitUpdate {
  version: string;
  hit: Hit;
}

export interface SocketEvent {
  event: {
    id: string;
    action: string;
    username: string;
  };
}
