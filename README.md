# Video Downloader Bot

Telegram бот для скачивания видео с YouTube и TikTok (без водяных знаков)
с системой подписок, выбором качества и веб-загрузкой больших файлов.

## Возможности

- **YouTube**: скачивание видео, shorts в любом доступном качестве
- **TikTok**: скачивание видео без водяных знаков
- **Выбор качества**: бот определяет все доступные качества и их размеры
- **Умная обработка больших файлов**:
  - Если файл < 2 ГБ → отправляется прямо в Telegram
  - Если файл > 2 ГБ, но есть меньшее качество < 2 ГБ → предлагает понизить
  - Если все качества > 2 ГБ → перенаправляет на веб-загрузку
- **Подписки**: пробный период + 3 платных плана (Telegram Stars)
- **Веб-интерфейс**: красивая страница для скачивания больших файлов
- **Админ-панель**: статистика и рассылка

## Структура

```
yt_bot/
├── bot.py                  # Главный файл — запуск бота и веб-сервера
├── config.py               # Конфигурация (из .env)
├── requirements.txt        # Зависимости
├── .env.example            # Пример переменных окружения
│
├── database/
│   ├── models.py           # SQLAlchemy модели (User, Subscription, History)
│   └── db.py               # CRUD-операции с БД
│
├── services/
│   ├── video_info.py       # Получение информации о видео (yt-dlp)
│   ├── downloader.py       # Скачивание видео
│   └── subscription.py     # Логика подписок и тарифов
│
├── handlers/
│   ├── start.py            # /start, меню, помощь
│   ├── download.py         # Обработка URL и загрузка видео
│   ├── subscription.py     # Управление подписками, оплата
│   └── admin.py            # Админ-панель
│
├── keyboards/
│   └── inline.py           # Inline-клавиатуры
│
├── middlewares/
│   └── subscription.py     # Проверка подписки перед загрузкой
│
├── web/
│   ├── app.py              # FastAPI приложение
│   ├── templates/          # HTML шаблоны
│   │   ├── index.html
│   │   ├── download.html
│   │   └── error.html
│   └── static/
│       └── style.css       # Стили (Modern Dark Theme)
│
├── utils/
│   └── helpers.py          # Утилиты
│
└── locales/
    └── messages.py         # Все тексты бота
```

## Установка

### 1. Клонируйте и установите зависимости

```bash
cd yt_bot
pip install -r requirements.txt
```

### 2. Настройте переменные окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:
- `BOT_TOKEN` — токен бота от @BotFather
- `ADMIN_IDS` — ваш Telegram ID (через запятую, если несколько)
- `WEB_BASE_URL` — URL вашего сервера для веб-загрузки
- `SECRET_KEY` — секретный ключ для токенов (любая длинная строка)

### 3. Установите FFmpeg (локально в проект)

Скачайте FFmpeg и положите в папку `ffmpeg/` в корне проекта:

```
yt_bot/
  ffmpeg/
    ffmpeg.exe
    ffprobe.exe
```

**Windows:**
1. Скачайте с https://www.gyan.dev/ffmpeg/builds/ (release essentials)
2. Распакуйте `ffmpeg.exe` и `ffprobe.exe` в папку `yt_bot/ffmpeg/`

**Linux:**
```bash
mkdir -p ffmpeg
wget -O ffmpeg.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
tar xf ffmpeg.tar.xz --strip-components=1 -C ffmpeg/ --wildcards '*/ffmpeg' '*/ffprobe'
rm ffmpeg.tar.xz
```

**macOS:**
```bash
mkdir -p ffmpeg
brew install ffmpeg --build-bottle
cp $(which ffmpeg) $(which ffprobe) ffmpeg/
```

Папка `ffmpeg/` создаётся автоматически при первом запуске бота — просто положите туда бинарники.

### 4. Запустите бота

```bash
python bot.py
```

Бот и веб-сервер запустятся одновременно.

## Тарифные планы

| План | Цена | Загрузок/день | Макс. качество |
|------|-------|---------------|----------------|
| 🆓 Пробный | Бесплатно (3 дня) | 3 | 1080p |
| ⭐ Basic | 99 Stars/мес | 10 | 1080p |
| 💎 Premium | 249 Stars/мес | 50 | 4K |
| 🚀 Pro | 499 Stars/мес | ∞ | 4K+ |

## Оплата

Бот использует **Telegram Stars** — встроенную валюту Telegram.
Пользователи оплачивают подписку прямо в боте без сторонних платёжных систем.

## Деплой

### VPS (рекомендуется)

1. Установите Python 3.11+, FFmpeg
2. Настройте `.env`
3. Запустите через `systemd` или `docker`
4. Настройте Nginx как reverse proxy для веб-сервера

### Docker

```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t yt-bot .
docker run -d --env-file .env -p 8080:8080 yt-bot
```
