import { uri as apiUri, hget, hpatch, joinAllUri, joinUri } from 'api';
import type { UserTags } from 'api/tags';

const BASE_URI = (): string => joinUri(apiUri(), 'status');

export type UserAvailability = 'available' | 'away' | 'busy' | 'unavailable';
export type UserStatusValue = UserAvailability;
export type ScheduleBlob = Record<string, string[]>;

export type UserStatus = {
  uname: string;
  name: string;
  status: UserStatusValue | null;
  schedule: string | null;
  team: string | null;
  tags?: UserTags;
};

export type PatchUserStatusBody = {
  status?: UserStatus['status'];
  schedule?: UserStatus['schedule'];
  team?: UserStatus['team'];
};

/**
 * Get list of all possible user status values
 * @return list of all possible user status values
 */
export const getStatuses = (): Promise<UserStatusValue[]> => {
  const path = joinUri(BASE_URI(), 'statuses');
  return hget(path);
};

/**
 * Get schedule blobs, where each key is a team name and each value is a list of schedules
 * @return schedule blobs, where each key is a team name and each value is a list of schedules
 */
export const getSchedules = (): Promise<ScheduleBlob> => {
  const path = joinUri(BASE_URI(), 'schedules');
  return hget(path);
};

/**
 * Get list of all users and their status information
 * @return list of all users and their status information
 ;*/
export const getUserStatuses = (): Promise<UserStatus[]> => {
  const path = joinAllUri(BASE_URI(), 'users');
  return hget(path);
};

/**
 * Get status information for a specific user
 * @param uname - username of the user whose status information is being requested
 ;* @return the status information for the specified user
 */
export const getUserStatus = (uname: string): Promise<UserStatus> => {
  const path = joinAllUri(BASE_URI(), 'users', uname);
  return hget(path);
};

/**
 * Update the status information for a specific user. Only the fields included in the body will be updated; all other fields will remain unchanged.
 ;* @param uname - username of the user whose status information is being updated
 * @param body - object containing the fields to be updated. Only the fields included in this object will be updated; all other fields will remain unchanged.
 * @returns the updated user status information after the patch has been applied
 */
export const patchUserStatus = (uname: string, body: PatchUserStatusBody): Promise<UserStatus> => {
  const path = joinAllUri(BASE_URI(), 'users', uname);
  return hpatch(path, body);
};
