/// <reference types="vitest" />
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  applyClassificationRules,
  canSeeGroups,
  canSeeRequired,
  defaultClassificationValidator,
  defaultDisabled,
  defaultParts,
  getLevelText,
  getMaxClassification,
  getParts,
  isAccessible,
  normalizedClassification,
  type ClassificationDefinition,
  type ClassificationParts
} from './classificationParser';

const classificationDefinition: ClassificationDefinition = {
  RESTRICTED: 'S//REL TO CAN',
  UNRESTRICTED: 'U',
  access_req_aliases: {
    CEO: ['CEO'],
    OC: ['ORCON'],
    ORCON: ['ORCON']
  },
  access_req_map_lts: {
    'CANADIAN EYES ONLY': 'CEO',
    'ORIGINATOR CONTROLLED': 'ORCON'
  },
  access_req_map_stl: {
    CEO: 'CANADIAN EYES ONLY',
    ORCON: 'ORIGINATOR CONTROLLED'
  },
  description: {},
  dynamic_groups: false,
  dynamic_groups_type: 'group',
  enforce: true,
  groups_aliases: {
    'CANADA ONLY': ['CAN'],
    FVEY: ['CAN', 'USA']
  },
  groups_auto_select: ['FVEY'],
  groups_auto_select_short: ['FVEY'],
  groups_map_lts: {
    CANADA: 'CAN',
    'FIVE EYES': 'FVEY',
    'UNITED STATES': 'USA'
  },
  groups_map_stl: {
    CAN: 'CANADA',
    FVEY: 'FIVE EYES',
    USA: 'UNITED STATES'
  },
  invalid_mode: false,
  levels_aliases: {
    PUBLIC: 'U'
  },
  levels_map: {
    '0': 'U',
    '1': 'C',
    '2': 'S',
    C: '1',
    S: '2',
    U: '0'
  },
  levels_map_lts: {
    CONFIDENTIAL: 'C',
    SECRET: 'S',
    UNCLASSIFIED: 'U'
  },
  levels_map_stl: {
    C: 'CONFIDENTIAL',
    S: 'SECRET',
    U: 'UNCLASSIFIED'
  },
  levels_styles_map: {},
  original_definition: {
    dynamic_groups: false,
    dynamic_groups_type: 'group',
    enforce: true,
    groups: [],
    levels: [],
    required: [],
    restricted: 'S//REL TO CAN',
    subgroups: [],
    unrestricted: 'U'
  },
  params_map: {
    ALPHA: {
      require_group: 'CAN'
    },
    BRAVO: {
      limited_to_group: 'USA'
    },
    CAN: {
      solitary_display_name: 'CANADA ONLY'
    },
    CEO: {
      is_required_group: true,
      require_lvl: 2
    }
  },
  subgroups_aliases: {
    ALPHA: ['ALPHA'],
    BRAVO: ['BRAVO']
  },
  subgroups_auto_select: ['ALPHA TEAM'],
  subgroups_auto_select_short: ['ALPHA'],
  subgroups_map_lts: {
    'ALPHA TEAM': 'ALPHA',
    'BRAVO TEAM': 'BRAVO'
  },
  subgroups_map_stl: {
    ALPHA: 'ALPHA TEAM',
    BRAVO: 'BRAVO TEAM'
  }
};

const cloneParts = (parts: ClassificationParts): ClassificationParts => ({
  lvlIdx: parts.lvlIdx,
  lvl: parts.lvl,
  req: [...parts.req],
  groups: [...parts.groups],
  subgroups: [...parts.subgroups]
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('classificationParser', () => {
  it('exposes stable empty defaults for parser state', () => {
    expect(defaultParts).toEqual({ lvlIdx: 0, lvl: '', req: [], groups: [], subgroups: [] });
    expect(defaultDisabled).toEqual({ groups: [], levels: [] });
    expect(defaultClassificationValidator).toEqual({ disabled: defaultDisabled, parts: defaultParts });
  });

  it('returns the short or long level label and reports unknown levels', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    expect(getLevelText(1, classificationDefinition, 'short', false)).toBe('C');
    expect(getLevelText(1, classificationDefinition, 'long', false)).toBe('CONFIDENTIAL');
    expect(getLevelText(99, classificationDefinition, 'short', false)).toBe('INVALID');
    expect(errorSpy).toHaveBeenCalledWith(
      "[classificationParser] Classification level number '99' was not found in your classification definition."
    );
  });

  it('parses levels, required markings, groups, and subgroups from short classifications', () => {
    const parts = getParts('C//OC/REL TO CAN, USA/ALPHA', classificationDefinition, 'short', false);

    expect(parts).toEqual({
      lvlIdx: 1,
      lvl: 'C',
      req: ['ORCON'],
      groups: ['CAN', 'USA'],
      subgroups: ['ALPHA']
    });
  });

  it('parses long-form classifications into long-form display values', () => {
    const parts = getParts(
      'CONFIDENTIAL//ORIGINATOR CONTROLLED/REL TO CANADA/ALPHA TEAM',
      classificationDefinition,
      'long',
      false
    );

    expect(parts).toEqual({
      lvlIdx: 1,
      lvl: 'CONFIDENTIAL',
      req: ['ORIGINATOR CONTROLLED'],
      groups: ['CANADA'],
      subgroups: ['ALPHA TEAM']
    });
  });

  it('checks required and group access using set semantics', () => {
    expect(canSeeRequired(['ORCON', 'CEO'], ['ORCON'])).toBe(true);
    expect(canSeeRequired(['ORCON'], ['ORCON', 'CEO'])).toBe(false);
    expect(canSeeGroups(['CAN', 'USA'], ['USA'])).toBe(true);
    expect(canSeeGroups(['CAN'], ['USA'])).toBe(false);
  });

  it('normalizes classifications with level escalation, solitary group names, and required groups', () => {
    const normalized = normalizedClassification(
      cloneParts({
        lvlIdx: 1,
        lvl: 'C',
        req: ['CEO'],
        groups: [],
        subgroups: ['ALPHA']
      }),
      classificationDefinition,
      'short',
      false,
      true
    );

    expect(normalized).toBe('S//CEO/CANADA ONLY/ALPHA');
  });

  it('returns the unrestricted label when enforcement is disabled or invalid mode is active', () => {
    expect(
      normalizedClassification(cloneParts(defaultParts), { ...classificationDefinition, enforce: false }, 'short', false)
    ).toBe('U');
    expect(
      normalizedClassification(cloneParts(defaultParts), { ...classificationDefinition, invalid_mode: true }, 'short', false)
    ).toBe('U');
  });

  it('applies classification rules to raise levels, add required groups, and disable incompatible options', () => {
    const result = applyClassificationRules(
      cloneParts({
        lvlIdx: 0,
        lvl: 'U',
        req: ['CEO'],
        groups: ['CAN', 'USA'],
        subgroups: ['BRAVO']
      }),
      classificationDefinition,
      'long',
      false
    );

    expect(result.parts.lvlIdx).toBe(2);
    expect(result.parts.lvl).toBe('SECRET');
    expect(result.parts.req).toEqual(['CANADIAN EYES ONLY']);
    expect(result.parts.groups).toEqual(['UNITED STATES']);
    expect(result.parts.subgroups).toEqual(['BRAVO TEAM']);
    expect(result.disabled.levels).toEqual(['CONFIDENTIAL', 'UNCLASSIFIED']);
    expect(result.disabled.groups).toContain('CANADA');
    expect(result.disabled.groups).toContain('FIVE EYES');
  });

  it('returns the most restrictive classification across two inputs', () => {
    const output = getMaxClassification(
      'C//ORCON/REL TO CAN/ALPHA',
      'S//REL TO CAN',
      classificationDefinition,
      'short',
      false
    );

    expect(output).toBe('S//ORCON//REL CAN, FVEY/ALPHA');
  });

  it('falls back to unrestricted max classification when enforcement is disabled', () => {
    expect(
      getMaxClassification('C//REL TO CAN', 'S//REL TO USA', { ...classificationDefinition, enforce: false }, 'short', false)
    ).toBe('U');
  });

  it('checks accessibility using level, required, group, and subgroup restrictions', () => {
    expect(isAccessible('S//ORCON/REL TO CAN/ALPHA', 'C//ORCON/REL TO CAN/ALPHA', classificationDefinition, true)).toBe(
      true
    );
    expect(isAccessible('C//REL TO CAN', 'S//REL TO CAN', classificationDefinition, true)).toBe(false);
    expect(isAccessible('S//REL TO USA', 'S//REL TO CAN', classificationDefinition, true)).toBe(false);
    expect(isAccessible('C//REL TO CAN', 'S//REL TO CAN', classificationDefinition, false)).toBe(true);
    expect(isAccessible('S//REL TO CAN', '', classificationDefinition, true)).toBe(true);
    expect(isAccessible('S//REL TO CAN', 'C//REL TO CAN', { ...classificationDefinition, invalid_mode: true }, true)).toBe(
      false
    );
  });
});
