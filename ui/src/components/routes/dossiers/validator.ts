import { iconExists } from '@iconify/react/dist/iconify.js';
import { uniqBy } from 'lodash-es';
import type { Dossier } from 'models/entities/generated/Dossier';
import { useTranslation } from 'react-i18next';

export const useValidator = () => {
  const { t, i18n } = useTranslation();

  return (dossier: Dossier, searchTotal: number, searchDirty: boolean) => {
    if (!dossier) {
      return t('route.dossiers.manager.validation.error');
    }

    if (!dossier.title) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.title') });
    }

    if (searchTotal < 0 || searchDirty) {
      return t('route.dossiers.manager.validation.search');
    }

    if (!dossier.query) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.query') });
    }

    if (!dossier.type) {
      return t('route.dossiers.manager.validation.error.missing', { field: t('route.dossiers.manager.field.type') });
    }

    if ((dossier.leads ?? []).length < 1 && (dossier.pivots ?? []).length < 1) {
      return t('route.dossiers.manager.validation.error.items');
    }

    for (const lead of dossier.leads ?? []) {
      if (!lead.label) {
        // You have not configured a lead label.
        return t('route.dossiers.manager.validation.error.leads.label');
      }

      if (!lead.label.en) {
        // You have not configured an english lead label.
        return t('route.dossiers.manager.validation.error.leads.label.en');
      }

      if (!lead.label.fr) {
        // You have not configured a french lead label.
        return t('route.dossiers.manager.validation.error.leads.label.fr');
      }

      if (!lead.format) {
        // You have not set the format for the lead with label <label>
        return t('route.dossiers.manager.validation.error.leads.format', { label: lead.label[i18n.language] });
      }

      if (!lead.content) {
        // You have not set the content for the lead with label <label>
        return t('route.dossiers.manager.validation.error.leads.content', { label: lead.label[i18n.language] });
      }

      if (!lead.icon || !iconExists(lead.icon)) {
        // You are missing an icon, or the specified icon does not exist for lead with label <label>
        return t('route.dossiers.manager.validation.error.leads.icon', { label: lead.label[i18n.language] });
      }
    }

    for (const pivot of dossier.pivots ?? []) {
      if (!pivot.label) {
        // You have not configured a pivot label.
        return t('route.dossiers.manager.validation.error.pivots.label');
      }

      if (!pivot.label.en) {
        // You have not configured an english pivot label.
        return t('route.dossiers.manager.validation.error.pivots.label.en');
      }

      if (!pivot.label.fr) {
        // You have not configured a french pivot label.
        return t('route.dossiers.manager.validation.error.pivots.label.fr');
      }

      if (!pivot.format) {
        // You have not set the format for the pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.format', { label: pivot.label[i18n.language] });
      }

      if (!pivot.value) {
        // You have not set the value for the pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.value', { label: pivot.label[i18n.language] });
      }

      if (!pivot.icon || !iconExists(pivot.icon)) {
        // You are missing an icon, or the specified icon does not exist for pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.icon', { label: pivot.label[i18n.language] });
      }

      if (!pivot.mappings || pivot.mappings.length < 1) {
        continue;
      }

      if ((pivot.mappings ?? []).length !== uniqBy(pivot.mappings ?? [], 'key').length) {
        // You have a duplicate for pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.duplicate', { label: pivot.label[i18n.language] });
      }

      if (pivot.mappings?.some(mapping => !mapping.key)) {
        // You have not configured a key for a mapping for pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.key', { label: pivot.label[i18n.language] });
      }

      if (pivot.mappings?.some(mapping => !mapping.field || (mapping.field === 'custom' && !mapping.custom_value))) {
        // You have not configured a field or custom value for a mapping for pivot with label <label>
        return t('route.dossiers.manager.validation.error.pivots.field', { label: pivot.label[i18n.language] });
      }
    }

    return null;
  };
};
