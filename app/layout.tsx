import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Xairex AI - Offline Neural Voice Assistant',
  description: 'Fully offline, CPU-only personal voice assistant for Windows',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-neural text-gray-100 font-mono">{children}</body>
    </html>
  )
}
