# 🐔 Chicken Trainer Web Ranking

線上排行榜 server，給閹雞訓練機 (Arduino Mega + WiFi 模組 D1 Mini) 用。

## Endpoints
- `GET /` 主頁
- `GET /api/leaderboard?limit=N` 取得排行榜
- `POST /api/sync` 上傳成績（D1 Mini 用）

## 本機跑
```bash
python3 server.py
# 預設 port 8080
```

## 雲端部署 (Render)
- 連 GitHub repo → 自動讀 `render.yaml`
- Free tier 免費使用
- URL: https://chicken-trainer-server.onrender.com（或自訂）
