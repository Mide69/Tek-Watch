import type { Metadata } from 'next'
import { Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google'
import { ThemeProvider } from '@/contexts/ThemeContext'
import './globals.css'

// Geometric grotesque with a slightly wide stance, the closest free match to
// the licensed face on the reference site, which we cannot use.
const sans = Plus_Jakarta_Sans({ subsets: ['latin'], variable: '--font-sans', weight: ['400', '500', '600', '700', '800'] })
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'TekWatch: AWS Monitoring and UK Compliance Checks for SMEs',
  description: 'AWS monitoring with anomaly detection, plain-English alerts, and automated checks mapped to UK GDPR, Cyber Essentials and ISO 27001, priced for SMEs, not enterprises.',
}

// Applies a saved dark preference before first paint. ThemeProvider only runs
// after hydration, so without this a dark-mode visitor saw the light theme
// flash on every page load. Must match STORAGE_KEY in ThemeContext.
const THEME_SCRIPT = `try{if(localStorage.getItem('tw-theme-v2')==='dark')document.documentElement.classList.add('dark')}catch(e){}`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className={`${sans.variable} ${jetbrainsMono.variable} font-sans`}>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  )
}
