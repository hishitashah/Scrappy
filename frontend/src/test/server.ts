/** MSW stands in for the API, so component tests never need a running backend. */

import { setupServer } from 'msw/node'

import { handlers } from './handlers'

export const server = setupServer(...handlers)
