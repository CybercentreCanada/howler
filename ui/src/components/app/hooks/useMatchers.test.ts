import { renderHook } from '@testing-library/react';
import type { Dossier } from 'models/entities/generated/Dossier';
import type { Hit } from 'models/entities/generated/Hit';
import type { Overview } from 'models/entities/generated/Overview';
import type { Template } from 'models/entities/generated/Template';
import type { WithMetadata } from 'models/WithMetadata';
import { useContextSelector } from 'use-context-selector';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HitContext } from '../providers/HitProvider';
import useMatchers from './useMatchers';

// Mock the useContextSelector hook
vi.mock('use-context-selector', () => ({
  useContextSelector: vi.fn(),
  createContext: vi.fn()
}));

// Mock lodash-es has function
vi.mock('lodash-es', () => ({
  has: vi.fn()
}));

// Create mock data
const mockTemplate: Template = {
  name: 'test-template',
  template: 'Test template content'
} as Template;

const mockOverview: Overview = {
  name: 'test-overview',
  overview: 'Test overview content'
} as Overview;

const mockDossiers: Dossier[] = [
  {
    name: 'test-dossier',
    description: 'Test dossier content'
  } as Dossier
];

const mockHit: Hit = {
  howler: {
    id: 'test-hit-id',
    analytic: 'test-analytic',
    data: {}
  }
} as Hit;

const mockHitWithMetadata: WithMetadata<Hit> = {
  ...mockHit,
  __template: mockTemplate,
  __overview: mockOverview,
  __dossiers: mockDossiers
};

const mockGetHit = vi.fn();

describe('useMatchers', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock useContextSelector to return our mock getHit function
    (useContextSelector as any).mockImplementation((context: any, selector: any) => {
      if (context === HitContext) {
        return selector({ getHit: mockGetHit });
      }
      return null;
    });
  });

  describe('getMatchingTemplate', () => {
    it('should return null when hit is null', async () => {
      const { result } = renderHook(() => useMatchers());

      const template = await result.current.getMatchingTemplate(null);

      expect(template).toBeNull();
    });

    it('should return null when hit is undefined', async () => {
      const { result } = renderHook(() => useMatchers());

      const template = await result.current.getMatchingTemplate(undefined);

      expect(template).toBeNull();
    });

    it('should return template from metadata when it exists', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(true);

      const { result } = renderHook(() => useMatchers());

      const template = await result.current.getMatchingTemplate(mockHitWithMetadata);

      expect(template).toBe(mockTemplate);
      expect(mockGetHit).not.toHaveBeenCalled();
    });

    it('should fetch hit with metadata when template is not present', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      const hitWithFetchedMetadata = { ...mockHit, __template: mockTemplate };
      mockGetHit.mockResolvedValue(hitWithFetchedMetadata);

      const { result } = renderHook(() => useMatchers());

      const template = await result.current.getMatchingTemplate(mockHit);

      expect(template).toBe(mockTemplate);
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });

    it('should handle getHit rejection gracefully', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      mockGetHit.mockRejectedValue(new Error('Failed to fetch hit'));

      const { result } = renderHook(() => useMatchers());

      await expect(result.current.getMatchingTemplate(mockHit)).rejects.toThrow('Failed to fetch hit');
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });
  });

  describe('getMatchingOverview', () => {
    it('should return null when hit is null', async () => {
      const { result } = renderHook(() => useMatchers());

      const overview = await result.current.getMatchingOverview(null);

      expect(overview).toBeNull();
    });

    it('should return null when hit is undefined', async () => {
      const { result } = renderHook(() => useMatchers());

      const overview = await result.current.getMatchingOverview(undefined);

      expect(overview).toBeNull();
    });

    it('should return overview from metadata when it exists', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(true);

      const { result } = renderHook(() => useMatchers());

      const overview = await result.current.getMatchingOverview(mockHitWithMetadata);

      expect(overview).toBe(mockOverview);
      expect(mockGetHit).not.toHaveBeenCalled();
    });

    it('should fetch hit with metadata when overview is not present', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      const hitWithFetchedMetadata = { ...mockHit, __overview: mockOverview };
      mockGetHit.mockResolvedValue(hitWithFetchedMetadata);

      const { result } = renderHook(() => useMatchers());

      const overview = await result.current.getMatchingOverview(mockHit);

      expect(overview).toBe(mockOverview);
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });

    it('should handle getHit rejection gracefully', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      mockGetHit.mockRejectedValue(new Error('Failed to fetch hit'));

      const { result } = renderHook(() => useMatchers());

      await expect(result.current.getMatchingOverview(mockHit)).rejects.toThrow('Failed to fetch hit');
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });
  });

  describe('getMatchingDossiers', () => {
    it('should return null when hit is null', async () => {
      const { result } = renderHook(() => useMatchers());

      const dossiers = await result.current.getMatchingDossiers(null);

      expect(dossiers).toBeNull();
    });

    it('should return null when hit is undefined', async () => {
      const { result } = renderHook(() => useMatchers());

      const dossiers = await result.current.getMatchingDossiers(undefined);

      expect(dossiers).toBeNull();
    });

    it('should return dossiers from metadata when they exist', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(true);

      const { result } = renderHook(() => useMatchers());

      const dossiers = await result.current.getMatchingDossiers(mockHitWithMetadata);

      expect(dossiers).toBe(mockDossiers);
      expect(mockGetHit).not.toHaveBeenCalled();
    });

    it('should fetch hit with metadata when dossiers are not present', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      const hitWithFetchedMetadata = { ...mockHit, __dossiers: mockDossiers };
      mockGetHit.mockResolvedValue(hitWithFetchedMetadata);

      const { result } = renderHook(() => useMatchers());

      const dossiers = await result.current.getMatchingDossiers(mockHit);

      expect(dossiers).toBe(mockDossiers);
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });

    it('should handle getHit rejection gracefully', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      mockGetHit.mockRejectedValue(new Error('Failed to fetch hit'));

      const { result } = renderHook(() => useMatchers());

      await expect(result.current.getMatchingDossiers(mockHit)).rejects.toThrow('Failed to fetch hit');
      expect(mockGetHit).toHaveBeenCalledWith('test-hit-id', true);
    });
  });

  describe('integration tests', () => {
    it('should correctly handle has function calls for different metadata properties', async () => {
      const { has } = await import('lodash-es');

      // Mock has to return true for __template, false for others
      (has as any).mockImplementation((_obj: any, prop: string) => {
        return prop === '__template';
      });

      const hitWithPartialMetadata = {
        ...mockHit,
        __template: mockTemplate
      };

      mockGetHit.mockResolvedValue({
        ...mockHit,
        __overview: mockOverview,
        __dossiers: mockDossiers
      });

      const { result } = renderHook(() => useMatchers());

      // Should return template from metadata
      const template = await result.current.getMatchingTemplate(hitWithPartialMetadata);
      expect(template).toBe(mockTemplate);

      // Should fetch overview
      const overview = await result.current.getMatchingOverview(hitWithPartialMetadata);
      expect(overview).toBe(mockOverview);

      // Should fetch dossiers
      const dossiers = await result.current.getMatchingDossiers(hitWithPartialMetadata);
      expect(dossiers).toBe(mockDossiers);

      // Verify has was called with correct parameters
      expect(has).toHaveBeenCalledWith(hitWithPartialMetadata, '__template');
      expect(has).toHaveBeenCalledWith(hitWithPartialMetadata, '__overview');
      expect(has).toHaveBeenCalledWith(hitWithPartialMetadata, '__dossiers');
    });

    it('should handle empty or undefined metadata gracefully', async () => {
      const { has } = await import('lodash-es');
      (has as any).mockReturnValue(false);

      mockGetHit.mockResolvedValue({
        ...mockHit,
        __template: undefined,
        __overview: null,
        __dossiers: []
      });

      const { result } = renderHook(() => useMatchers());

      const template = await result.current.getMatchingTemplate(mockHit);
      const overview = await result.current.getMatchingOverview(mockHit);
      const dossiers = await result.current.getMatchingDossiers(mockHit);

      expect(template).toBeUndefined();
      expect(overview).toBeNull();
      expect(dossiers).toEqual([]);
      expect(mockGetHit).toHaveBeenCalledTimes(3);
    });

    it('should maintain referential equality of returned functions', () => {
      const { result, rerender } = renderHook(() => useMatchers());

      const firstRender = {
        getMatchingTemplate: result.current.getMatchingTemplate,
        getMatchingOverview: result.current.getMatchingOverview,
        getMatchingDossiers: result.current.getMatchingDossiers
      };

      rerender();

      const secondRender = {
        getMatchingTemplate: result.current.getMatchingTemplate,
        getMatchingOverview: result.current.getMatchingOverview,
        getMatchingDossiers: result.current.getMatchingDossiers
      };

      // Functions should be the same reference due to useCallback
      expect(firstRender.getMatchingTemplate).toBe(secondRender.getMatchingTemplate);
      expect(firstRender.getMatchingOverview).toBe(secondRender.getMatchingOverview);
      expect(firstRender.getMatchingDossiers).toBe(secondRender.getMatchingDossiers);
    });
  });
});
