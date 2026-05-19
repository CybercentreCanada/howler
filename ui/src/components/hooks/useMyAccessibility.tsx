import type { ReactNode } from 'react';

import type { AppAccessibilityPreferences } from '@tui/a11y';

// Add/remove accessibility buttons from this list to have them in the app
// Each button should use the AccessibilityButton component provided in order to be properly formatted/added
const accessibilityFeatures: ReactNode[] = [];

// Modify web accessibility preferences to manage the default features
const accessibilityPreferences: AppAccessibilityPreferences = {
  enableAccessibility: true,
  enableAnimation: true,
  enableCursor: true,
  enableLineHeight: true,
  enableTextAlignment: true,
  enableTextSize: true,
  enableTextSpacing: true,
  enableTooltipLeaveDelay: true
};

export type MyAccessibilityType = {
  features: ReactNode[];
  preferences: AppAccessibilityPreferences;
};

// Export the preferences and accessibility features you want shown/active in the application
export const useMyAccessibility = (): MyAccessibilityType => {
  return {
    features: accessibilityFeatures,
    preferences: accessibilityPreferences
  };
};
