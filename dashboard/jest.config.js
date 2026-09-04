const nextJest = require('next/jest')

const createJestConfig = nextJest({ dir: './' })

/** @type {import('jest').Config} */
const config = {
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.test.ts', '**/__tests__/**/*.test.tsx'],
  // next/jest infers this from tsconfig's paths for real imports, but
  // jest.mock('@/...') calls are hoisted above those imports and resolved
  // through jest's own resolver before that inference runs, so a mocked
  // alias needs the mapping spelled out explicitly.
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
}

module.exports = createJestConfig(config)
