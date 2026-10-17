# Xairex Website

Official website for Xairex AI - Fully offline neural voice assistant.

## Deploy to Vercel

1. Create GitHub repo: `Xenoz-GitHub/xairex-website`
2. Push this code to that repo
3. Go to [Vercel](https://vercel.com)
4. Click "Add New Project"
5. Import `xairex-website` repo
6. Add environment variables:
   - `DATABASE_URL` = `postgresql://neondb_owner:npg_rLpv2OZBUq0m@ep-restless-cell-b5kvfwh2.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require`
   - `ADMIN_PIN` = `1346251346795846`
   - `NEXT_PUBLIC_SITE_URL` = `https://xairex-ai.vercel.app`
7. Deploy

## Features

- Neural-core animated visualizer
- Secret admin page at `/xenozexe`
- Geolocation logging
- CLI installation guide
- Mobile responsive
- Dark terminal aesthetic

## Tech Stack

- Next.js 15
- React 19
- Framer Motion
- Tailwind CSS
- Neon PostgreSQL

## Local Development

```bash
npm install
npm run dev
```

Visit http://localhost:3000
