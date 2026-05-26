# Tek Watch Dashboard

Customer-facing web application for viewing AWS infrastructure metrics.

## Tech Stack

- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript (strict mode)
- **Styling:** Tailwind CSS + Shadcn/ui
- **Charts:** Recharts
- **Auth:** AWS Amplify (Cognito)
- **Data Fetching:** SWR
- **HTTP Client:** Axios

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
npm install
```

### Environment Variables

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_COGNITO_REGION=eu-west-2
NEXT_PUBLIC_COGNITO_USER_POOL_ID=your-user-pool-id
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=your-app-client-id
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Build

```bash
npm run build
npm start
```

### Lint

```bash
npm run lint
```

### Type Check

```bash
npm run type-check
```

## Project Structure

```
dashboard/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home (redirects)
│   │   ├── login/              # Login page
│   │   ├── overview/           # Dashboard overview
│   │   ├── compute/            # Compute resources
│   │   ├── databases/          # Database resources
│   │   ├── networking/         # Networking resources
│   │   ├── storage/            # Storage resources
│   │   ├── messaging/          # Messaging resources
│   │   ├── security/           # Security resources
│   │   ├── cost/               # Cost analysis
│   │   └── alerts/             # Alerts management
│   ├── components/             # React components
│   │   ├── ui/                 # Shadcn/ui components
│   │   ├── charts/             # Chart components
│   │   ├── tables/             # Table components
│   │   └── layout/             # Layout components
│   ├── lib/                    # Utilities
│   │   ├── api.ts              # API client
│   │   ├── auth.ts             # Auth helpers
│   │   └── utils.ts            # Utility functions
│   └── hooks/                  # Custom React hooks
│       ├── useAuth.ts
│       ├── useMetrics.ts
│       └── useAlerts.ts
├── public/                     # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## Features

### Implemented
- [x] Login page with Customer ID + Password
- [x] Overview page with summary cards
- [x] API client with JWT authentication
- [x] Utility functions (formatting, colors, etc.)
- [x] Responsive layout
- [x] TypeScript strict mode

### TODO
- [ ] Complete authentication with Cognito
- [ ] All service pages (compute, databases, etc.)
- [ ] Time-series charts with Recharts
- [ ] Resource detail drilldown
- [ ] Alerts panel
- [ ] Region filter
- [ ] Real-time updates with SWR
- [ ] Mobile navigation
- [ ] Dark mode toggle
- [ ] Export functionality
- [ ] Search and filtering

## Code Style

- Use TypeScript strict mode
- No `any` types
- Function components only
- Tailwind CSS for styling (no inline styles)
- Absolute imports with `@/` prefix

## Authentication Flow

1. User enters Customer ID + Password
2. Authenticate with Cognito
3. Receive JWT token
4. Store token in localStorage
5. Include token in all API requests
6. Redirect to `/overview` on success

## API Integration

All API calls go through `src/lib/api.ts`:

```typescript
import apiClient from '@/lib/api'

// Set token after login
apiClient.setToken(jwtToken)

// Make API calls
const overview = await apiClient.getOverview()
const ec2 = await apiClient.getEC2Instances('eu-west-2')
```

## Deployment

### Vercel (Recommended)

```bash
vercel
```

### AWS Amplify

```bash
amplify init
amplify add hosting
amplify publish
```

### Docker

```bash
docker build -t tek-watch-dashboard .
docker run -p 3000:3000 tek-watch-dashboard
```

## Contributing

1. Create feature branch
2. Make changes
3. Run `npm run lint` and `npm run type-check`
4. Submit PR

## License

Proprietary - Tek Tribe Ltd
