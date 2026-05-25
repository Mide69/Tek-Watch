# Dashboard Testing Guide

This guide explains how to test the Tribe Watch dashboard locally.

---

## Prerequisites

- Node.js 18+ installed
- npm or yarn installed
- Backend API running (or mock data)

---

## Setup

### 1. Install Dependencies

```bash
cd dashboard
npm install
```

### 2. Configure Environment Variables

Create a `.env.local` file in the `dashboard` directory:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_COGNITO_REGION=eu-west-2
NEXT_PUBLIC_COGNITO_USER_POOL_ID=your-user-pool-id
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=your-app-client-id
```

For local testing without Cognito, you can use placeholder values.

### 3. Start Development Server

```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

---

## Testing Checklist

### ✅ Navigation
- [ ] Click on each sidebar item
- [ ] Verify correct page loads
- [ ] Check active state highlighting
- [ ] Test mobile sidebar (toggle open/close)

### ✅ Login Page (`/login`)
- [ ] Enter Customer ID in format `TT-XXXX`
- [ ] Enter password
- [ ] Click "Sign in"
- [ ] Verify validation errors for invalid format
- [ ] Check "Forgot password?" link

### ✅ Overview Page (`/overview`)
- [ ] Verify summary cards display
- [ ] Check agent status banner
- [ ] Verify loading state shows spinner
- [ ] Check empty states for alarms/findings

### ✅ Compute Page (`/compute`)
- [ ] Verify EC2 instances table
- [ ] Check Lambda functions table
- [ ] Verify ECS services table
- [ ] Test with empty data (no resources)
- [ ] Check status badges (running, stopped, etc.)

### ✅ Databases Page (`/databases`)
- [ ] Verify RDS instances table
- [ ] Check DynamoDB tables table
- [ ] Verify Multi-AZ badges
- [ ] Check storage formatting (bytes to GB/TB)

### ✅ Networking Page (`/networking`)
- [ ] Verify placeholder sections display
- [ ] Check "Coming soon" messages
- [ ] Verify icons render correctly

### ✅ Storage Page (`/storage`)
- [ ] Verify S3 buckets table
- [ ] Check versioning/encryption badges
- [ ] Verify summary cards (total buckets, objects, size)
- [ ] Check empty state

### ✅ Messaging Page (`/messaging`)
- [ ] Verify SQS queues table
- [ ] Check SNS topics table
- [ ] Verify FIFO/Standard badges
- [ ] Check message age highlighting (red if > 1 hour)
- [ ] Verify delivery rate calculation

### ✅ Security Page (`/security`)
- [ ] Verify GuardDuty findings
- [ ] Check IAM summary cards
- [ ] Verify ACM certificates table
- [ ] Check CloudWatch alarms list
- [ ] Verify severity badges

### ✅ Cost Page (`/cost`)
- [ ] Verify summary cards (MTD, Forecast, Last Month)
- [ ] Check trend indicators (up/down arrows)
- [ ] Verify service breakdown
- [ ] Check percentage bars
- [ ] Verify chart placeholder

### ✅ Alerts Page (`/alerts`)
- [ ] Verify alert list displays
- [ ] Test filter buttons (All, Active, Acknowledged)
- [ ] Click "Acknowledge" button
- [ ] Verify severity badges
- [ ] Check empty state (no alerts)

### ✅ Agent Page (`/agent`)
- [ ] Verify agent status display
- [ ] Check health badge (Healthy/Degraded/Unhealthy)
- [ ] Verify collection metrics cards
- [ ] Check regions list
- [ ] Verify collectors grid
- [ ] Wait 30 seconds to test auto-refresh

---

## Testing with Mock Data

If the backend API is not running, you can test with mock data by modifying the API client to return static data.

### Example: Mock EC2 Data

Edit `dashboard/src/lib/api.ts`:

```typescript
async getEC2Instances(region?: string) {
  // Mock data for testing
  return {
    instances: [
      {
        resource_id: 'i-0abc123def456',
        resource_name: 'web-server-1',
        instance_type: 't3.medium',
        state: 'running',
        az: 'us-east-1a',
        cpu_percent: 45.2,
      },
      {
        resource_id: 'i-0def456abc789',
        resource_name: 'api-server-1',
        instance_type: 't3.large',
        state: 'running',
        az: 'us-east-1b',
        cpu_percent: 72.8,
      },
    ],
  }
}
```

---

## Testing Responsive Design

### Desktop (1920x1080)
- [ ] Sidebar always visible
- [ ] Tables fit without horizontal scroll
- [ ] Cards display in grid layout

### Tablet (768x1024)
- [ ] Sidebar always visible
- [ ] Tables may scroll horizontally
- [ ] Cards stack in 2 columns

### Mobile (375x667)
- [ ] Sidebar hidden by default
- [ ] Hamburger menu button visible
- [ ] Sidebar slides in from left
- [ ] Tables scroll horizontally
- [ ] Cards stack in 1 column

---

## Testing Error States

### Network Error
1. Stop the backend API
2. Navigate to any page
3. Verify error message displays
4. Check console for error logs

### Invalid Token
1. Set an invalid JWT token in localStorage
2. Navigate to any page
3. Verify redirect to login page

### Empty Data
1. Return empty arrays from API
2. Verify "No data" messages display
3. Check icons and styling

---

## Performance Testing

### Page Load Time
- [ ] Overview page loads in < 2 seconds
- [ ] Service pages load in < 2 seconds
- [ ] No layout shift during load

### Data Fetching
- [ ] Loading spinner shows immediately
- [ ] Data appears within 1 second (local API)
- [ ] No duplicate API calls

### Memory Usage
- [ ] Open DevTools > Performance
- [ ] Navigate between pages
- [ ] Check for memory leaks
- [ ] Verify no excessive re-renders

---

## Browser Compatibility

Test in the following browsers:

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile Safari (iOS)
- [ ] Mobile Chrome (Android)

---

## Accessibility Testing

### Keyboard Navigation
- [ ] Tab through all interactive elements
- [ ] Press Enter to activate buttons
- [ ] Press Escape to close modals (when implemented)

### Screen Reader
- [ ] Test with NVDA (Windows) or VoiceOver (Mac)
- [ ] Verify all content is announced
- [ ] Check ARIA labels

### Color Contrast
- [ ] Use browser DevTools to check contrast ratios
- [ ] Verify WCAG AA compliance (4.5:1 for text)

---

## Known Issues

### Not Yet Implemented
- Cognito authentication (login redirects without validation)
- Charts (placeholders shown)
- Region filter (dropdown doesn't filter data)
- SWR caching (data fetched on every page load)
- Resource drilldown (tables not clickable)

### Workarounds
- For testing, use mock data in API client
- Skip login page by navigating directly to `/overview`
- Manually refresh page to reload data

---

## Reporting Issues

If you find bugs or issues:

1. Check console for errors
2. Note the page and action that caused the issue
3. Take a screenshot if visual bug
4. Document steps to reproduce
5. Report to development team

---

## Next Steps After Testing

Once testing is complete:

1. **Fix any bugs** found during testing
2. **Implement Cognito** authentication
3. **Add Recharts** for visualizations
4. **Implement SWR** for caching
5. **Add region filter** functionality
6. **Build Admin Portal**

---

**Happy Testing!** 🚀
