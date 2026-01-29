import { useClueActionsSelector, useClueEnrichSelector } from '@cccsaurora/clue-ui';
import { adaptSchema } from '@cccsaurora/clue-ui/components/actions/form/schemaAdapter';
import type { JsonSchema, JsonSchema7 } from '@jsonforms/core';
import { materialCells, materialRenderers } from '@jsonforms/material-renderers';
import { JsonForms } from '@jsonforms/react';
import {
  Autocomplete,
  createTheme,
  Divider,
  Stack,
  TextField,
  ThemeProvider,
  Typography,
  useTheme
} from '@mui/material';
import { ApiConfigContext } from 'components/app/providers/ApiConfigProvider';
import type { PivotFormProps } from 'components/routes/dossiers/PivotForm';
import ErrorBoundary from 'components/routes/ErrorBoundary';
import { flatten, unflatten } from 'flat';
import type { JSONSchema7 } from 'json-schema';
import capitalize from 'lodash-es/capitalize';
import cloneDeep from 'lodash-es/cloneDeep';
import isBoolean from 'lodash-es/isBoolean';
import isEqual from 'lodash-es/isEqual';
import isPlainObject from 'lodash-es/isPlainObject';
import merge from 'lodash-es/merge';
import omitBy from 'lodash-es/omitBy';
import pick from 'lodash-es/pick';
import pickBy from 'lodash-es/pickBy';
import type { Pivot } from 'models/entities/generated/Pivot';
import { useCallback, useContext, useMemo, type FC } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Enhanced material renderers wrapped in ErrorBoundary components to prevent
 * form rendering errors from crashing the entire application
 */
const WRAPPED_RENDERERS = materialRenderers.map(value => ({
  ...value,
  renderer: ({ ...props }) => (
    <ErrorBoundary>
      <value.renderer {...props} />
    </ErrorBoundary>
  )
}));

/**
 * CluePivotForm Component
 *
 * A form component that allows users to configure pivot operations for Clue actions.
 * This component provides a dynamic form interface for selecting and configuring
 * Clue actions with their associated parameters and field mappings.
 *
 * Key Features:
 * - Action selection via autocomplete dropdown
 * - Dynamic form generation based on action schemas
 * - Field mapping configuration for hit indexes
 * - Custom value support for non-standard fields
 * - Integration with JsonForms for complex parameter handling
 *
 * @param props - Component props containing pivot data and update callback
 * @returns JSX element representing the pivot configuration form
 */

const CluePivotForm: FC<PivotFormProps> = ({ pivot, update }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { config } = useContext(ApiConfigContext);

  // Get available Clue actions from the global state
  const actions = useClueActionsSelector(ctx => ctx?.availableActions);
  const ready = useClueEnrichSelector(ctx => ctx.ready);

  /**
   * Generates a dynamic JSON schema for the selected action's parameters.
   * This schema is used to render the form fields for action configuration.
   *
   * The function:
   * 1. Retrieves the action definition based on the pivot value
   * 2. Adapts the action's parameter schema using Clue's schema adapter
   * 3. Enhances string properties with hit index enums for autocomplete
   * 4. Applies any extra schema definitions from the action
   */
  const formSchema = useMemo(() => {
    const value = pivot?.value;

    // Return null if no action is selected or action doesn't exist
    if (!value || !actions[value]) {
      return null;
    }

    // Clone and adapt the action's parameter schema
    const clueAdaptedSchema = cloneDeep({
      ...adaptSchema(actions[value].params),
      ...(actions[value].extra_schema ?? {})
    });

    // Enhance string properties with hit index options for better UX
    Object.entries(clueAdaptedSchema.properties).forEach(([key, prop]) => {
      // Handle boolean properties by converting to enum with hit indexes
      if (typeof prop === 'boolean') {
        clueAdaptedSchema.properties[key] = { enum: Object.keys(config.indexes.hit) };
        return;
      }

      if (prop.type === 'array') {
        if (isBoolean(prop.items)) {
          clueAdaptedSchema.properties[key] = { enum: Object.keys(config.indexes.hit) };
          return;
        } else if (!Array.isArray(prop.items)) {
          prop.type = prop.items.type;
          delete prop.items;
        }
      }

      // Skip non-string properties
      if (prop.type !== 'string' && (!Array.isArray(prop.type) || !prop.type.includes('string'))) {
        return;
      }

      // Strip date-time format since we're picking from a list of fields
      if (prop.format === 'date-time') {
        delete prop.format;
      }

      // Add hit index options to string properties without existing enums
      if (!prop.enum && !prop.oneOf) {
        prop.enum = Object.keys(config.indexes.hit);
      }
    });

    return clueAdaptedSchema;
  }, [actions, config.indexes.hit, pivot?.value]);

  /**
   * Generates the UI schema for JsonForms based on the form schema.
   * This defines the layout and rendering options for each form field.
   *
   * The UI schema:
   * 1. Creates a vertical layout for all form elements
   * 2. Sorts fields by custom order property or required status
   * 3. Configures autocomplete for enum fields
   * 4. Applies custom options and rules from the schema
   */
  const uiSchema = useMemo(
    () => ({
      type: 'VerticalLayout',
      elements: Object.entries(formSchema?.properties ?? {})
        // Sort fields: first by custom order, then by required status
        .sort(([a_key, a_ent], [b_key, b_ent]) => {
          if (!!(a_ent as any).order || !!(b_ent as any).order) {
            return (a_ent as any).order - (b_ent as any).order;
          } else {
            // Required fields appear first
            return +formSchema?.required.includes(a_key) - +formSchema?.required.includes(b_key);
          }
        })
        .map(([key, value]) => ({
          type: 'Control',
          scope: `#/properties/${key}`,
          options: {
            // Enable autocomplete for fields with enum values
            autocomplete: !!(value as JSONSchema7).enum || !!(value as JSONSchema7).oneOf,
            showUnfocusedDescription: true,
            // Apply any custom options from the schema
            ...(value as any).options
          },
          // Apply conditional rendering rules if present
          rule: (value as any).rule
        }))
    }),
    [formSchema?.properties, formSchema?.required]
  );

  /**
   * Handles updates to the selected action value.
   * When an action is selected, this function:
   * 1. Sets up default field mappings based on action requirements
   * 2. Configures selector mappings for actions that don't accept empty inputs
   * 3. Updates the pivot configuration
   *
   * @param value - The selected action identifier
   */
  const onUpdate = useCallback(
    (value: string) => {
      const mappings: Pivot['mappings'] = [];

      // TODO: Fix type hints and remove the any cast
      // For actions that don't accept empty inputs, add selector mapping
      if (!(actions[value] as any).accept_empty) {
        // Use 'selectors' for multiple selection, 'selector' for single selection
        mappings.push({
          key: actions[value].accept_multiple ? 'selectors' : 'selector',
          field: 'howler.id'
        });
      }

      update({
        value,
        mappings
      });
    },
    [actions, update]
  );

  /**
   * Transforms pivot mappings into form data format for JsonForms.
   * Converts the mappings array into a key-value object where:
   * - Key is the mapping key (e.g., 'selector', 'selectors')
   * - Value is either the custom_value (if set) or the field name
   */
  const formData = useMemo(() => {
    const rawData = Object.fromEntries(
      (pivot?.mappings ?? []).map(mapping => {
        const parameterSchema = actions[pivot.value]?.params?.properties?.[mapping.key];
        const value = mapping.custom_value ?? mapping.field;

        if (mapping.field === 'custom') {
          if ((parameterSchema as JsonSchema7)?.type === 'number') {
            return [mapping.key, parseFloat(mapping.custom_value)];
          }

          if ((parameterSchema as JsonSchema7)?.type === 'integer') {
            return [mapping.key, Math.floor(parseFloat(mapping.custom_value))];
          }

          return [mapping.key, mapping.custom_value];
        }

        return [mapping.key, value];
      })
    );

    // JSONForms will inadvertently nest dicts
    // (e.g. "abc1.field" key will result in)
    // {
    //   "abc1": {
    //     "field"
    //   }
    // }
    // Validation doesn't account for this, so we need to merge the flattened and unflattened dicts.
    // This leads to awful side effects in the onChange function, detailed there.
    return merge({}, rawData, unflatten(rawData));
  }, [actions, pivot?.mappings, pivot.value]);

  // Find the main selector mapping for special handling in the UI
  const selectorMapping = pivot?.mappings?.find(_mapping => ['selector', 'selectors'].includes(_mapping.key));

  return (
    <ErrorBoundary>
      {/* Action Selection Dropdown */}
      <Autocomplete
        fullWidth
        disabled={!pivot || !ready}
        options={Object.entries(actions)
          .filter(([_key, definition]) => !!definition && definition.format == 'pivot')
          .map(([key]) => key)}
        renderOption={({ key, ...optionProps }, actionId) => {
          const definition = actions[actionId];

          return (
            <Stack component="li" key={key} {...optionProps} spacing={1}>
              {/* Action name and ID display */}
              <Stack direction="row" spacing={1} alignSelf="start" alignItems="center">
                <Typography>{definition.name}</Typography>
                <pre
                  style={{
                    fontSize: '0.85rem',
                    border: `thin solid ${theme.palette.divider}`,
                    padding: theme.spacing(0.5),
                    borderRadius: theme.shape.borderRadius
                  }}
                >
                  {actionId}
                </pre>
              </Stack>
              {/* Action description */}
              <Typography variant="body2" color="text.secondary" alignSelf="start">
                {definition.summary}
              </Typography>
            </Stack>
          );
        }}
        getOptionLabel={opt => actions[opt]?.name ?? ''}
        renderInput={params => (
          <TextField {...params} size="small" fullWidth label={t('route.dossiers.manager.pivot.value')} />
        )}
        value={pivot?.value ?? ''}
        onChange={(_ev, value) => onUpdate(value)}
      />

      <Divider flexItem />

      {/* Field Mappings Section */}
      <Typography>{t('route.dossiers.manager.pivot.mappings')}</Typography>

      {/* Selector Field Mapping - Special handling for the main selector */}
      {selectorMapping && (
        <>
          <Autocomplete
            fullWidth
            options={['custom', ...Object.keys(config.indexes.hit)]}
            renderInput={params => (
              <TextField
                {...params}
                size="small"
                fullWidth
                label={capitalize(selectorMapping.key)}
                sx={{ minWidth: '150px' }}
              />
            )}
            value={selectorMapping.field}
            onChange={(_ev, field) =>
              update({
                mappings: pivot.mappings.map(_mapping =>
                  _mapping.key === selectorMapping.key ? { ..._mapping, field } : _mapping
                )
              })
            }
          />

          {/* Custom Value Input - Shown when 'custom' is selected */}
          {selectorMapping.field === 'custom' && (
            <TextField
              size="small"
              label={t('route.dossiers.manager.pivot.mapping.custom')}
              disabled={!pivot}
              value={selectorMapping?.custom_value ?? null}
              onChange={ev =>
                update({
                  mappings: pivot.mappings.map(_mapping =>
                    _mapping.key === selectorMapping.key ? { ..._mapping, custom_value: ev.target.value } : _mapping
                  )
                })
              }
            />
          )}
        </>
      )}

      {/* Dynamic Form for Action Parameters */}
      {formSchema && (
        <ThemeProvider
          theme={_theme =>
            createTheme({
              ..._theme,
              components: {
                MuiTextField: {
                  defaultProps: { size: 'small' },
                  styleOverrides: { root: { marginTop: theme.spacing(1) } }
                },
                MuiInputBase: {
                  defaultProps: { size: 'small' }
                },
                MuiFormControl: {
                  defaultProps: { size: 'small' },
                  styleOverrides: {
                    root: { marginTop: theme.spacing(1) }
                  }
                }
              }
            })
          }
        >
          <ErrorBoundary>
            <JsonForms
              schema={formSchema as JsonSchema}
              uischema={uiSchema}
              renderers={WRAPPED_RENDERERS}
              cells={materialCells}
              data={formData}
              onChange={({ data }) => {
                // We now need to remove the unflattened object we provided for validation to JSON forms
                // EXCEPT, new keys are added via nesting. So we need to flatten the nested data and overwrite it
                // with the flat data.
                const flatData: { [index: string]: any } = omitBy(data, isPlainObject);
                const nestedData = flatten(pickBy(data, isPlainObject)) as { [index: string]: any };

                // Merge existing selector mappings with new form data. This is the crazy complexity I mentioned above.
                //
                // The full flow:
                // 1. A field mapping is chosen, e.g. 'key.1': 'howler.id'
                // 2. The data object has the structure {key: {1: 'howler.id'}}
                // 3. This is added to fullData via nestedData
                // 4. Another field mapping is chosen, e.g. 'key.2': 'howler.id'
                // 5. The data object now looks like: {key.1: 'howler.id', key: {1: 'howler.id', 2: 'howler.id'}}
                // 6. We integrate this again, but this time the existing `key.1` key overwrites
                //    the flattened `key: {1}` object.
                // 7. When 'key.1' is changed, the ROOT (flattened) key changes, but the outdated variant is still there.
                //    that is: {key.1: 'howler.status', key.2: 'howler.id', key: {1: 'howler.id', 2: 'howler.id'}}
                // 8. This is why the flat data is AFTER the nested data. So that the final, resolved object is:
                //    {key.1: 'howler.status', key.2: 'howler.id'}
                //
                // This is very confusing - ask Matt R if you need a better explanation.
                const fullData = { ...nestedData, ...flatData, ...pick(pivot.mappings, ['selector', 'selectors']) };

                // Convert form data back to mappings format
                const newMappings = Object.entries(fullData).map(([key, val]: [string, any]) => ({
                  key,
                  // Use 'custom' field type if value is not a standard hit index
                  field: val in config.indexes.hit ? val : 'custom',
                  // Store custom values separately from field names
                  custom_value: val in config.indexes.hit ? null : val
                }));

                // Only update if mappings have actually changed (performance optimization)
                if (!isEqual(newMappings, pivot.mappings)) {
                  update({ mappings: newMappings });
                }
              }}
              config={{}}
            />
          </ErrorBoundary>
        </ThemeProvider>
      )}
    </ErrorBoundary>
  );
};

export default CluePivotForm;
