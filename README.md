# 個資確認系統 (Personal Info Confirmation)

給學校註冊組使用的個資確認網站。取代用一張紙傳閱全班個資的舊作法。

## 三種角色

| 角色 | 權限 |
|------|------|
| 學生 (`student`) | 看自己的個資、確認資料正確、留備註反映錯誤 |
| 學藝股長 (`officer`) | 看全班「確認進度」(只有姓名、座號、是否確認)，**看不到別人的個資**；自己也要確認 |
| 註冊組長 (`registrar`) | 看全班完整個資、可修正、可重置確認狀態、可匯出 JSON |

## 測試帳號

```
test01     / test01      ← 1 號學生
test02     / test02      ← 2 號學生
...
test30     / test30      ← 30 號學生
officer01  / officer01   ← 學藝股長（兼任 13 號學生）
registrar01 / registrar01 ← 註冊組長
```

## 本機跑起來

```bash
cd StudentInfoConfirm
python3 server.py
```

預設 port = `8765`。打開瀏覽器：<http://localhost:8765>

## 重新產生假資料

```bash
python3 seed.py
```

## 檔案結構

```
StudentInfoConfirm/
├── server.py              ← Python http.server (stdlib only)
├── seed.py                ← 假資料產生器 (隨機種子=20260429 可重現)
├── data/
│   ├── students.json      ← 30 位學生個資
│   ├── users.json         ← 32 個帳號
│   └── classroom.json     ← 班級資訊
└── static/
    ├── index.html         ← SPA (含登入 / 學生 / 學藝 / 註冊組四頁)
    ├── styles.css
    └── app.js             ← Vanilla JS, no framework
```

## API 路由

| Method | Path | 權限 | 用途 |
|--------|------|------|------|
| POST | `/api/login` | — | 登入 |
| POST | `/api/logout` | — | 登出 |
| GET | `/api/me` | — | 取得當前 user |
| GET | `/api/classroom` | 任 | 取得班級資訊 |
| GET | `/api/student/me` | 學生/學藝 | 自己的個資 |
| POST | `/api/student/confirm` | 學生/學藝 | 確認自己個資正確 |
| POST | `/api/student/note` | 學生/學藝 | 寫備註反映錯誤 |
| GET | `/api/class/status` | 學藝/註冊組 | 全班確認狀態 (公開欄位) |
| GET | `/api/students/all` | 註冊組 | 全班完整個資 |
| POST | `/api/registrar/edit` | 註冊組 | 修正某筆個資 |
| POST | `/api/registrar/reset_confirm` | 註冊組 | 重置某筆確認狀態 |

## 安全設計

- 密碼用 SHA-256 雜湊存放 (`password_hash`)，不以明文儲存
- Session 用隨機 token (`secrets.token_urlsafe(24)`) + HttpOnly cookie
- 學藝股長 API 只回傳 `name / seat / confirmed` 三欄，後端強制過濾 (前端拿不到隱私欄位)
- 寫入前用 `_LOCK` 保護，避免並發衝突
- 寫檔用 `os.replace(tmp, p)` 確保原子性

## 部署到 Render

跟原本的閹雞 server 一樣：

1. 在 Render 上指向 GitHub repo
2. Build Command: 留空 (純 stdlib)
3. Start Command: `python3 server.py`
4. Environment Variable: `PORT` 由 Render 自動注入
