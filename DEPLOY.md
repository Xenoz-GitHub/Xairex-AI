# Deploy Instructions

## Step 1: Create GitHub Repo

1. Go to https://github.com/new
2. Repository name: `xairex-website`
3. Public
4. DO NOT initialize with README (we have one)
5. Create repository

## Step 2: Push Code

In PowerShell from xairex-web directory:

```powershell
git remote add origin https://github.com/Xenoz-GitHub/xairex-website.git
git branch -M main
git push -u origin main
```

## Step 3: Deploy on Vercel

1. Go to https://vercel.com/dashboard
2. Click "Add New" → "Project"
3. Import `Xenoz-GitHub/xairex-website`
4. Framework: Next.js (auto-detected)
5. Click "Environment Variables"
6. Add these **three** variables:

**DATABASE_URL**:
```
postgresql://neondb_owner:npg_rLpv2OZBUq0m@ep-restless-cell-b5kvfwh2.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

**ADMIN_PIN**:
```
1346251346795846
```

**NEXT_PUBLIC_SITE_URL**:
```
https://xairex-ai.vercel.app
```

7. Click "Deploy"
8. Wait 2-3 minutes

## Step 4: Configure Custom Domain

1. In Vercel dashboard, click on your deployed project
2. Go to "Settings" → "Domains"
3. Add domain: `xairex-ai.vercel.app`
4. Vercel will configure it automatically

## Done!

Your website will be live at https://xairex-ai.vercel.app

### Testing

- Landing page: https://xairex-ai.vercel.app
- CLI page: https://xairex-ai.vercel.app/cli
- Admin login: https://xairex-ai.vercel.app/xenozexe
  - PIN: 1346251346795846
- Admin dashboard: https://xairex-ai.vercel.app/xenozexe/dashboard

### Troubleshooting

**Build fails?**
- Check environment variables are set correctly
- Make sure DATABASE_URL has no extra spaces

**Admin login doesn't work?**
- Ensure ADMIN_PIN environment variable is set
- Clear browser cookies
- Try incognito mode

**Neural-core animation not showing?**
- Check browser console for errors
- Ensure JavaScript is enabled
- Try different browser

## What You Get

- Professional landing page with neural-core animation
- CLI installation guide
- Secret admin panel with geolocation logging
- Mobile-responsive design
- Dark terminal aesthetic
- Zero emojis (as requested)
