import type { TagCategory } from 'api/tags';

export const TAG_CATEGORY_OPTIONS = [
  { value: 'portfolio', labelKey: 'tsxUserTags.drawer.category.portfolio' },
  { value: 'products', labelKey: 'tsxUserTags.drawer.category.products' },
  { value: 'primary_disciplines', labelKey: 'tsxUserTags.drawer.category.disciplines' }
] satisfies { value: TagCategory; labelKey: string }[];
