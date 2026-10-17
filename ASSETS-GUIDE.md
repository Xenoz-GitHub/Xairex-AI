# Xairex Website - Assets Guide

## 📸 Brand Assets Location & Usage

### 1. Icon - `iconxairex.png`

**File Details:**
- **Path:** `c:\Users\SuarezJ\Documents\MIDNIGHT-PROJECT\xairex-web\public\iconxairex.png`
- **Size:** 1,048,475 bytes (1.0 MB)
- **Format:** PNG
- **Status:** ✅ Deployed

**Usage in Website:**
```tsx
// In app/layout.tsx - Browser tab icon
<link rel="icon" href="/iconxairex.png" />

// Can also be used in components
<img src="/iconxairex.png" alt="Xairex AI" />
```

**Where It Appears:**
- Browser tab/favicon
- Mobile home screen icon
- Bookmark icon
- Can be used in hero section or footer

---

### 2. Banner - `banner.png`

**File Details:**
- **Path:** `c:\Users\SuarezJ\Documents\MIDNIGHT-PROJECT\xairex-web\public\banner.png`
- **Size:** 1,417,151 bytes (1.35 MB)
- **Format:** PNG
- **Status:** ✅ Deployed

**Usage in Website:**
```css
/* In app/globals.css - Body background */
body {
  background-image: url('/banner.png');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}
```

**Where It Appears:**
- Full-page background (fixed)
- Visible behind all content
- Neural core animation overlays it
- Responsive across all screen sizes

---

## 🗂️ Complete Assets Inventory

### Brand Assets (User-Provided)
```
public/
├── iconxairex.png    1,048,475 bytes  [Brand Icon]
└── banner.png        1,417,151 bytes  [Background Banner]
```

### Next.js Default Assets (Auto-Generated)
```
public/
├── file.svg          391 bytes        [File icon placeholder]
├── globe.svg         1,035 bytes      [Globe icon placeholder]
├── next.svg          1,375 bytes      [Next.js logo]
├── vercel.svg        128 bytes        [Vercel logo]
└── window.svg        385 bytes        [Window icon placeholder]
```

---

## 🎨 How to Access Assets in Code

### From React Components
```tsx
// Direct path (public folder is root)
<img src="/iconxairex.png" alt="Xairex" />
<img src="/banner.png" alt="Background" />

// With Next.js Image component
import Image from 'next/image';

<Image 
  src="/iconxairex.png" 
  alt="Xairex AI"
  width={100}
  height={100}
/>
```

### From CSS Files
```css
/* Direct URL reference */
.hero {
  background-image: url('/banner.png');
}

.icon {
  background-image: url('/iconxairex.png');
}
```

### From Metadata (SEO)
```tsx
// In app/layout.tsx
export const metadata = {
  title: 'Xairex AI',
  icons: {
    icon: '/iconxairex.png',
    apple: '/iconxairex.png',
  },
  openGraph: {
    images: ['/banner.png'],
  },
}
```

---

## 🌐 Asset URLs (When Deployed)

### Production URLs
```
Icon:   https://xairex-ai.vercel.app/iconxairex.png
Banner: https://xairex-ai.vercel.app/banner.png
```

### Current Deployment URLs
```
Icon:   https://xairex-qbrioufb9-xenoz-githubs-projects.vercel.app/iconxairex.png
Banner: https://xairex-qbrioufb9-xenoz-githubs-projects.vercel.app/banner.png
```

---

## 🔍 Verify Assets Are Live

### Method 1: Direct Browser Access
1. Open browser
2. Navigate to: `https://xairex-qbrioufb9-xenoz-githubs-projects.vercel.app/iconxairex.png`
3. Should display the icon image
4. Navigate to: `https://xairex-qbrioufb9-xenoz-githubs-projects.vercel.app/banner.png`
5. Should display the banner image

### Method 2: Check Network Tab
1. Open website in browser
2. Press F12 (Developer Tools)
3. Go to Network tab
4. Look for `iconxairex.png` and `banner.png` requests
5. Should show 200 status (success)

### Method 3: View Page Source
1. Right-click on page → View Page Source
2. Search for "iconxairex.png" (Ctrl+F)
3. Should find it in `<link rel="icon">`
4. Search for "banner.png"
5. Should find it in CSS background

---

## 📊 Asset Optimization (Future)

### Current Status: ❌ Not Optimized
- PNG format (lossless, large file size)
- No compression applied
- No WebP/AVIF alternatives

### Recommended Optimizations:
1. **Convert to WebP** - 30-50% smaller file size
   ```bash
   # Using imagemagick or similar tool
   convert iconxairex.png iconxairex.webp
   convert banner.png banner.webp
   ```

2. **Create Multiple Sizes** - For responsive design
   ```
   iconxairex-16x16.png   (favicon)
   iconxairex-32x32.png   (favicon)
   iconxairex-192x192.png (mobile)
   iconxairex-512x512.png (PWA)
   ```

3. **Use Next.js Image Optimization**
   ```tsx
   import Image from 'next/image';
   
   <Image 
     src="/banner.png"
     alt="Background"
     fill
     priority
     quality={85}
   />
   ```

---

## 🚀 Adding New Assets

### Step 1: Place File in `public/`
```bash
# Copy to public directory
cp /path/to/new-image.png xairex-web/public/
```

### Step 2: Reference in Code
```tsx
// In any component
<img src="/new-image.png" alt="Description" />
```

### Step 3: Commit and Deploy
```bash
git add public/new-image.png
git commit -m "Add new image asset"
vercel --prod
```

---

## 📁 File Structure

```
xairex-web/
├── public/              ← All static assets go here
│   ├── iconxairex.png   ← Brand icon (1.0 MB)
│   ├── banner.png       ← Background (1.35 MB)
│   ├── file.svg
│   ├── globe.svg
│   ├── next.svg
│   ├── vercel.svg
│   └── window.svg
├── app/
│   ├── layout.tsx       ← Uses iconxairex.png (favicon)
│   ├── globals.css      ← Uses banner.png (background)
│   ├── page.tsx
│   └── ...
└── ...
```

---

## ✅ Checklist: Assets Deployed Successfully

- [x] `iconxairex.png` copied to `public/`
- [x] `banner.png` copied to `public/`
- [x] Icon referenced in `layout.tsx`
- [x] Banner referenced in `globals.css`
- [x] Files committed to git
- [x] Deployed to Vercel
- [ ] Verified assets load in browser (waiting for deployment)
- [ ] Tested on mobile devices (pending)
- [ ] Optimized for performance (future task)

---

**Last Updated:** October 17, 2026 (20:10 SGT)  
**Asset Status:** ✅ All assets deployed, awaiting Vercel build completion
