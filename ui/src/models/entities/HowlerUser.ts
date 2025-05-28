import type { AppUser } from 'commons/components/app/AppUserService';

export interface HowlerUser extends AppUser {
  name: string;
  email: string;
  username: string;
  api_quota?: number;
  classification?: string;
  apikeys?: [string, string[], string][];
  groups?: string[];
  roles?: string[];
  type: string[];
  has_password?: boolean;
  is_active?: boolean;
  favourite_views?: string[];
  favourite_analytics?: string[];
  dashboard?: { entry_id: string; type: 'view' | 'analytic'; config: string }[];
}
