# Render-এ SpaceAgriSim ডিপ্লয় — ধাপে ধাপে (বাংলা)

এই ডকুমেন্টটা হাতে-কলমে Follow করার জন্য। ইংরেজি টেকনিক্যাল রেফারেন্স আলাদা ফাইলে আছে:
[`docs/PHASE13_RENDER_DEPLOYMENT.md`](PHASE13_RENDER_DEPLOYMENT.md)।

সবকিছু Render-এর **free plan** ধরে লেখা। খরচ: **$0**, কিন্তু ফ্রি প্ল্যানের তিনটা সীমা আছে (নিচে §৮-এ)।

---

## ধাপ ০ — যা যা হাতে থাকতে হবে (৫ মিনিট)

| জিনিস | কেন দরকার |
|---|---|
| GitHub repo `meherabmehu/SpaceAgriSim`, branch `main` | Render এই repo থেকেই build করে |
| Render অ্যাকাউন্ট (GitHub দিয়ে login) | free, কার্ড লাগে না |
| একটা ব্রাউজার ট্যাব খোলা: `https://dashboard.render.com` | কাজের মাঝে বারবার লাগবে |

**আগে নিশ্চিত হয়ে নিন কোডটা push করা আছে।** এই ডকুমেন্ট যে কমিটে আছে, সেটাই deploy হবে:

```bash
git fetch origin && git log --oneline -1 origin/main
```

`origin/main`-এ `render.yaml` থাকতে হবে। না থাকলে বাকি ধাপগুলো কাজ করবে না।

> ⚠️ **অর্ডারটা খুবই গুরুত্বপূর্ণ:** আগে **ডেটাবেস**, তারপর **Blueprint**।
> উল্টো করলে API প্রথমবার database URL ছাড়া চালু হবে, আর ওই ভুলটা পরে ঠিক করা ঝামেলার।

---

## ধাপ ১ — Postgres ডেটাবেস তৈরি করুন (৩ মিনিট)

1. ড্যাশবোর্ডে উপরের ডান দিকের **New +** → **Postgres**।
2. ঘরগুলো এভাবে ভরুন:
   - **Name:** `spaceagrisim-db`
   - **Database:** `spaceagrisim` (ডিফল্ট থাকলে থাক)
   - **User:** `spaceagrisim` (ডিফল্ট থাকলে থাক)
   - **Region:** **Singapore** ← API-ও Singapore-এ হবে, একই region হলে ইন্টারনাল নেটওয়ার্কে কথা বলে (দ্রুত + বাইরে খোলা থাকে না)
   - **Postgres Version:** ডিফল্ট যেটা আছে সেটাই রাখুন
   - **Instance Type:** **Free**
3. **Create Database** চাপুন। ১–২ মিনিটে `Available` হবে।
4. ডেটাবেসের পেজে নিচে **Connections** সেকশনে যান। দুটো URL দেখবেন:
   - **Internal Database URL** ← এটা লাগবে
   - External Database URL ← এটা **লাগবে না**

5. **Internal Database URL** কপি করুন। দেখতে এমন হবে:

   ```
   postgres://spaceagrisim:AbCdEf123456@dpg-xxxxxxxxxxxx-a:5432/spaceagrisim
   ```

6. ⚠️ **হাত দিয়ে দুইটা জায়গা বদলাতে হবে।** URL-এর শুরুটা হবে:

   ```
   postgresql+psycopg://spaceagrisim:AbCdEf123456@dpg-xxxxxxxxxxxx-a:5432/spaceagrisim
   ```

   অর্থাৎ:
   - `postgres://` → `postgresql+psycopg://`
   - `postgresql://` লেখা থাকলে → `postgresql+psycopg://`
   - বাকি পুরোটা (ইউজার, পাসওয়ার্ড, হোস্ট, পোর্ট, ডেটাবেসের নাম) **হুবহু** থাকবে।

   কেন: অ্যাপের SQLAlchemy ড্রাইভার `psycopg` (v3), পুরনো `postgres://` স্কিম চিনবে না — চালু হয়েই ক্র্যাশ করবে।

👉 এই সাজানো URL-টা একটা টেক্সট ফাইলে রাখুন। ধাপ ৪-এ লাগবে।

---

## ধাপ ২ — Blueprint চালু করুন (২ মিনিট)

`render.yaml` ফাইলে দুইটা সার্ভিসের পুরো বর্ণনা আগেই লেখা আছে: `spaceagrisim-api` (Python) আর `spaceagrisim-web` (static)। তাই ম্যানুয়ালি সার্ভিস বানাতে হবে না।

1. **New +** → **Blueprint**।
2. repo লিস্ট থেকে **SpaceAgriSim** সিলেক্ট করুন → **Connect**।
3. **Blueprint Name:** `spaceagrisim`
4. **Branch:** `main`
5. Render `render.yaml` পড়ে দুইটা সার্ভিস দেখাবে — **`spaceagrisim-api`** আর **`spaceagrisim-web`**।
6. এবার **Apply** চাপলে Render তিনটা ভ্যালু চাইবে (পরের ধাপ)। ⚠️ Apply চাপার **আগে** নিচের তিনটা ভ্যালু রেডি রাখুন।

> Render যদি বলে "no Blueprint file found": repo-র **root**-এ `render.yaml` আছে কিনা দেখুন (সাবফোল্ডারে থাকলে ধরবে না)।

---

## ধাপ ৩ — তিনটা ভ্যালু বসান (২ মিনিট)

Blueprint স্ক্রিনে (অথবা পরে সার্ভিস → **Environment**) এই তিনটা `sync: false` ভ্যারিয়েবল খালি দেখাবে। **হুবহু** নিচের ফরম্যাটে দিন:

### ৩.১ `SPACEAGRISIM_DATABASE_URL` — (API সার্ভিসের ভ্যারিয়েবল)

ধাপ ১-এ সাজানো Internal URL। উদাহরণ:

```
postgresql+psycopg://spaceagrisim:AbCdEf123456@dpg-xxxxxxxxxxxx-a:5432/spaceagrisim
```

❌ `postgres://` দিয়ে শুরু করবেন না। ❌ External URL দেবেন না (Render-এর বাইরে থেকে কানেক্ট করতে অনেক ধীর, আর free instance-এ external access বন্ধও হতে পারে)।

### ৩.২ `SPACEAGRISIM_CORS_ORIGINS` — (API সার্ভিসের ভ্যারিয়েবল)

```
["https://spaceagrisim-web.onrender.com"]
```

তিনটা নিয়ম, নাহলে ব্রাউজারে CORS error:

- **JSON লিস্ট**, একেবারে স্কয়ার ব্র্যাকেট ও ডাবল কোটেশন সহ — শুধু URL লিখলে হবে না
- স্ল্যাশ (`/`) দিয়ে শেষ হবে না
- `*` (wildcard) দেবেন না — অ্যাপ সেটা রিজেক্ট করে

> সার্ভিসের নাম যদি বদলান, এই URL-ও বদলাতে হবে। Render-এর দেওয়া লম্বা URL (`https://spaceagrisim-web-xxxx.onrender.com`) হলে সেটাই বসান।

### ৩.৩ `VITE_API_BASE_URL` — (⚠️ **web** সার্ভিসের ভ্যারিয়েবল, API-র না)

```
https://spaceagrisim-api.onrender.com/api
```

- দুইটা জিনিস **অবশ্যই** থাকতে হবে: `https://` আর শেষে `/api`
- শুধু `spaceagrisim-api.onrender.com` দিলে সাইট খুলবে কিন্তু সব ডেটা আসবে না (silent failure)
- এটা **build-time** ভ্যালু — বান্ডলে ঢুকে যায়। বদলালে **rebuild** লাগবে, শুধু restart-এ কাজ হবে না

তারপর **Apply**।

---

## ধাপ ৪ — API deploy করুন (৫–৮ মিনিট)

1. Blueprint Apply করার পর Render দুইটা সার্ভিসই তৈরি করবে, কিন্তু `autoDeployTrigger: 'off'` থাকায় নিজে থেকে deploy হবে না।
2. `spaceagrisim-api` সার্ভিসে ঢুকে ডান দিকে **Manual Deploy** → **Deploy latest commit**।
3. **Logs** ট্যাবে দেখুন। সফল হলে শেষে এমন লাইন আসবে:

   ```
   Application startup complete.
   Uvicorn running on http://0.0.0.0:10000
   ```

4. প্রথম deploy-এ `pip install` চলবে, ৩–৫ মিনিট লাগতে পারে। Free instance-এ build ধীর।
5. স্ট্যাটাস **Live** হলে ব্রাউজারে টেস্ট করুন:

   ```
   https://spaceagrisim-api.onrender.com/api/ready
   ```

   কাঙ্ক্ষিত উত্তর (HTTP 200):

   ```json
   {"status":"ready","database":"available","database_backend":"postgresql", ...}
   ```

   এখানে `"database": "available"` না দেখলে **থামুন** — §৭ দেখুন।

> ⚠️ প্রথম রিকোয়েস্টে ৩০–৬০ সেকেন্ড লাগতে পারে। Free instance ১৫ মিনিট নিষ্ক্রিয় থাকলে ঘুমিয়ে পড়ে, আবার জাগতে ~১ মিনিট লাগে। এটা স্বাভাবিক, কোনো bug না।

**API Live হলে ব্রাউজার ট্যাবটা বন্ধ করবেন না — web deploy-এর আগে এটা লাগবে।**

---

## ধাপ ৫ — Web (frontend) deploy করুন (৪–৬ মিনিট)

1. `spaceagrisim-web` সার্ভিসে ঢুকুন।
2. **Environment** ট্যাবে গিয়ে নিশ্চিত করুন `VITE_API_BASE_URL` = `https://spaceagrisim-api.onrender.com/api` (ধাপ ৩.৩) আর `NODE_VERSION` = `22`।
3. **Manual Deploy** → **Deploy latest commit**।
4. Logs-এ `npm ci` → `vite build` → `dist/` তৈরি হবে। শেষে `Uploading...` / `Published` দেখবেন।
5. Live হলে খুলুন: `https://spaceagrisim-web.onrender.com`

---

## ধাপ ৬ — কানেকশন যাচাই (২ মিনিট)

সাইট খুলে এই তিনটা দেখুন:

1. **উপরের ব্যাজে "API connected"** (সবুজ)। লাল/ধূসর থাকলে = `VITE_API_BASE_URL` ভুল বা API ঘুমিয়ে আছে → আগে `/api/ready` ব্রাউজারে একবার খুলে জাগিয়ে নিন, তারপর সাইট refresh করুন।
2. **Model explorer** খুলে accession লিস্ট লোড হচ্ছে কিনা (২৬টা accession)।
3. একটা **নতুন analysis চালান** (যেমন lettuce-earth-growth) — রেজাল্ট আসা উচিত। এটা DB write করে, তাই একসাথে Postgres-ও টেস্ট হয়ে যায়।

### Acceptance path (৫টা ধাপ, এক মিনিটে)

| # | কাজ | প্রত্যাশিত ফল |
|---|---|---|
| ১ | Assistant-কে জিজ্ঞেস করুন: "What is the expected crop yield on the Moon?" | উত্তর `partial`, reason `unsupported-premise` — বানানো সংখ্যা দেবে না |
| ২ | Mizuna "absolute load" মডেল দেখুন | `disabled` অবস্থায়, কারণ-সহ |
| ৩ | একটা CSV export করুন | হেডারে লেখা থাকবে এটা **model output, measurement নয়** |
| ৪ | Model explorer খুলুন | ২৬টা accession লোড হয় |
| ৫ | Assistant-এ কোনো NASA dataset-এর সোর্স জিজ্ঞেস করুন | citation সহ উত্তর |

---

## ধাপ ৭ — সমস্যা হলে (symptom → কারণ → সমাধান)

| যা দেখছেন | আসল কারণ | সমাধান |
|---|---|---|
| Build fail: `No module named ...` | `backend/requirements.txt` মিসিং বা build command ভুল | Build command = `pip install -r backend/requirements.txt` |
| Deploy fail: secret সংক্রান্ত error | `SPACEAGRISIM_AUTH_SECRET` সেট হয়নি | Blueprint-এ `generateValue: true` আছে কিনা দেখুন; ম্যানুয়াল হলে একটা র‍্যান্ডম স্ট্রিং দিন |
| `/api/ready` → `database: unavailable` | DB URL ভুল স্কিম / External URL / DB এখনো Available হয়নি | `postgresql+psycopg://` দিয়ে শুরু কিনা দেখুন, Internal URL ব্যবহার করুন |
| ক্র্যাশ: `ModuleNotFoundError: psycopg` | URL-এ ড্রাইভার ঠিক আছে কিন্তু `psycopg` ইনস্টল হয়নি | `backend/requirements.txt`-এ `psycopg[binary]` আছে কিনা দেখুন |
| সাইট খোলে, কিন্তু সব ডেটা খালি | `VITE_API_BASE_URL`-এ `/api` বা `https://` নেই | ঠিক করে **rebuild** করুন (restart নয়) |
| ব্রাউজারে CORS error | `SPACEAGRISIM_CORS_ORIGINS` বনাম web-এর আসল origin মিলছে না | হুবহু origin, JSON লিস্ট, শেষে স্ল্যাশ নয় |
| Refresh করলে 404 | SPA rewrite নেই | `routes: /* → /index.html` আছে কিনা দেখুন |
| প্রথম লোডে ৫০+ সেকেন্ড | Free instance ঘুমিয়ে ছিল | স্বাভাবিক। চাইলে paid plan |
| কিছুক্ষণ পরে অ্যাকাউন্ট/analysis হারিয়ে গেল | SQLite ব্যবহার হচ্ছে (Postgres URL বসানো হয়নি) | `SPACEAGRISIM_DATABASE_URL` বসিয়ে redeploy |

---

## ধাপ ৮ — ফ্রি প্ল্যানের সীমা (মুখে বলে দেওয়ার মতো)

1. **১৫ মিনিট নিষ্ক্রিয় থাকলে ঘুমিয়ে পড়ে**, আবার জাগতে ~১ মিনিট। প্রথম ভিজিটারে ধীর লাগবে।
2. **Free Postgres ৩০ দিন পরে এক্সপায়ার হয়** (এরপর ~১৪ দিন grace period)। ডেটা রাখতে চাইলে সময়মতো paid-এ আপগ্রেড বা ডেটা export করতে হবে।
3. **RAM ৫১২ MB, CPU ০.১** — single worker (`--workers 1`) ইচ্ছাকৃত: in-process rate limiter আর SQLite path একই worker-এ coherent থাকে।
4. **Postgres না বসালে** SQLite ফাইলে ডেটা যায়, আর free instance-এর disk ephemeral — প্রতিবার restart/spin-down-এ অ্যাকাউন্ট ও analysis মুছে যাবে। তাই §১ আর §৩.১ বাদ দেওয়া যাবে না।
5. **Deploy নিজে থেকে হয় না** (`autoDeployTrigger: 'off'`) — প্রতিবার নিজে Manual Deploy চাপতে হবে। এটা ইচ্ছাকৃত, যাতে অর্ধেক-কাজ করা commit হঠাৎ live না হয়ে যায়।

---

## ধাপ ৯ — deploy-এর পরে

- **পরিবর্তন push করলে:** API → Manual Deploy; web → Manual Deploy (rebuild লাগবে, কারণ `VITE_*` build-time)।
- **`VITE_API_BASE_URL` বদলালে:** শুধু restart নয়, **rebuild**।
- **সার্ভিসের নাম বদলালে:** `SPACEAGRISIM_CORS_ORIGINS` আর `VITE_API_BASE_URL` দুইটাই আপডেট + দুই সার্ভিসই redeploy।
- **লোকালে টেস্ট করা যায় এভাবে** (আসল Render-এ না গিয়ে):

  ```bash
  SPACEAGRISIM_ENVIRONMENT=production \
  SPACEAGRISIM_AUTH_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  uvicorn app.main:app --app-dir backend --port 8123
  ```

  তারপর `http://127.0.0.1:8123/api/ready`।

> **সৎ সীমা:** এখানে যেসব যাচাইয়ের কথা বলা হয়েছে, সেগুলো লোকাল production-mode boot আর টেস্ট স্যুটে (৫৩৫ passed / ১ skipped) করা। **Render-এর আসল ইনফ্রারেস্ট্রাকচারে ডিপ্লয় আমি চালিয়ে দেখিনি** — তাই প্রথম deploy-এর সময় log দেখে §৭ ধরে এগোনোই সঠিক পথ।
