# 🚀 Railway.app Deploy গাইড — CleanAudioTube

## ধাপ ১ — GitHub Repository বানান

1. **github.com** এ যান, নতুন account বানান (যদি না থাকে)
2. নতুন repository বানান:
   - নাম: `cleanaudiotube`
   - Public রাখুন
   - "Create repository" click করুন

3. এই ফাইলগুলো upload করুন (drag & drop করুন GitHub-এ):

```
CleanAudioTube/
├── Dockerfile
├── railway.toml
├── requirements.txt
├── backend/
│   ├── main.py
│   ├── processing.py
│   └── utils.py
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

---

## ধাপ ২ — Railway.app এ Deploy করুন

1. **railway.app** এ যান
2. "Start a New Project" click করুন
3. "Deploy from GitHub repo" select করুন
4. GitHub দিয়ে login করুন
5. আপনার `cleanaudiotube` repo select করুন
6. Railway automatically Dockerfile detect করবে
7. **"Deploy"** click করুন

✅ Railway নিজেই সব install করবে!

---

## ধাপ ৩ — Volume যোগ করুন (গুরুত্বপূর্ণ!)

Processing এর সময় temporary files store করতে হবে:

1. Railway dashboard এ আপনার project open করুন
2. "Add Volume" click করুন
3. Mount path দিন: `/app/backend/work`
4. Save করুন

---

## ধাপ ৪ — URL পান

Deploy শেষে Railway একটা URL দেবে:
```
https://cleanaudiotube-production.up.railway.app
```

এই URL browser এ open করুন — আপনার app ready! 🎉

---

## ⏱️ প্রথমবার Deploy কত সময় লাগবে?

| কাজ | সময় |
|-----|------|
| Docker build | ~5-8 মিনিট |
| Demucs model download | ~3-5 মিনিট |
| **মোট** | **~10-15 মিনিট** |

পরের বার deploy মাত্র ~2 মিনিট।

---

## 💰 Railway Free Tier কতটুকু পাবেন?

- **$5/মাস free credit** (নতুন account এ)
- CPU processing এ যথেষ্ট
- ৫ মিনিটের video process করতে ~$0.05 লাগে

---

## ❓ সমস্যা হলে

**"Application failed to start"** দেখালে:
- Railway logs দেখুন (View Logs button)
- সাধারণত ffmpeg বা demucs install issue

**Video process হচ্ছে না:**
- `/health` endpoint এ যান: `https://your-app.railway.app/health`
- সব dependency "true" দেখাচ্ছে কিনা check করুন

---

## 📞 সাহায্য দরকার?

Railway Discord: discord.gg/railway
Railway Docs: docs.railway.app
