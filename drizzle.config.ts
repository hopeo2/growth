import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  schema: './src/db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL ?? '',
  },
  // The `auth` schema is managed by Supabase; only own the `public` schema.
  schemaFilter: ['public'],
  verbose: true,
  strict: true,
})
