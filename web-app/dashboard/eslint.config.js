import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'node_modules'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { 'react-hooks': reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
    },
  },
  {
    // shadcn components are generated and committed as-is.
    files: ['src/components/ui/**'],
    rules: { 'react-hooks/purity': 'off' },
  },
  {
    files: ['*.config.{ts,js}'],
    languageOptions: { globals: globals.node },
  },
)
