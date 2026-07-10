import type { UserAvailability } from 'api/status';
import type { TsxColoredDotColor } from 'plugins/tsx_components/tsx_colored_dot';

export const isUserAvailability = (value: unknown): value is UserAvailability =>
  typeof value === 'string' && ['available', 'away', 'busy', 'unavailable'].includes(value);

export const getAvailabilityColor = (status: UserAvailability): TsxColoredDotColor => {
  switch (status) {
    case 'available':
      return 'green';
    case 'away':
      return 'yellow';
    case 'busy':
      return 'red';
    case 'unavailable':
    default:
      return 'gray';
  }
};
