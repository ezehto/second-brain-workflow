import { createCn } from 'cn/config'

/** The type scale (index.css `--text-*` tokens); also the legacy `.t-*` aliases. */
const TYPE_SCALE = ['numeral', 'caption', 'small', 'body', 'panel', 'page', 'date'] as const

/**
 * Class merging that knows the type scale: `text-caption` is a font size, not a
 * colour, so it replaces another size and never deletes a text colour.
 */
export const cn = createCn({
  extend: {
    classGroups: {
      'font-size': [{ text: [...TYPE_SCALE] }, ...TYPE_SCALE.map((name) => `t-${name}`)],
    },
  },
})

