import { uri as apiUri, hget, hput, joinUri } from 'api';

const BASE_URI = (): string => joinUri(apiUri(), 'status/users');

export type UserStatus = {
  uname: string;
  name: string;
  status: string | null;
};

export function getUserStatuses(): Promise<UserStatus[]> {
  return hget(BASE_URI());
}

export function getUserStatus(uname: string): Promise<UserStatus> {
  return hget(joinUri(BASE_URI(), uname));
}

export function updateUserStatus(uname: string, status: UserStatus['status']): Promise<UserStatus> {
  return hput(joinUri(BASE_URI(), uname), { status });
}
