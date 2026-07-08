import type { OperatorNumber, UserAvailability } from 'api/status';
import type { TsxColoredDotColor } from 'plugins/tsx_components/tsx_colored_dot';

export const isOperatorNumber = (value: unknown): value is OperatorNumber =>
  typeof value === 'string' && Number.isInteger(Number(value)) && Number(value) > 0 && Number(value) <= 15;

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
