# AI Seller - Интеллектуальный AI-продавец

**AI Seller** — это интеллектуальный продавец-консультант для интернет-магазинов светодиодных линз и автомобильной оптики. Система способна консультировать клиентов, подбирать товары, работать с возражениями и помогать оформить заказ через различные каналы связи (Telegram, веб-виджет, API).

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.12+
- Docker и Docker Compose
- (Опционально) Ollama для локальных моделей

### Установка

1. **Клонируйте репозиторий**:
```bash
git clone <repository-url>
cd ai-seller
```

2. **Создайте файл окружения**:
```bash
cp .env.example .env
# Отредактируйте .env согласно вашей конфигурации
```

3. **Установите зависимости**:
```bash
# Используя Poetry
poetry install

# Или pip
pip install -e .
```

4. **Запустите инфраструктуру**:
```bash
docker-compose up -d
```

5. **Инициализируйте базу данных**:
```bash
# Внутри контейнера или локально
alembic upgrade head
```

6. **Запустите приложение**:
```bash
uvicorn app.main:app --reload
```

### Установка на Mac Intel без Docker (всё в `goinfre` — проверено)

Машина без Docker, с ограниченной домашней квотой; весь проект и все инструменты
живут в `goinfre` (на 42-школе это `/Users/<user>/goinfre` → `$HOME/goinfre`).
Реально проверено на таком же Mac: Python miniforge + brew в `goinfre`,
родной бинарник Qdrant, Ollama локально, а LLM — OpenAI-совместимый сервер
GigaChat 21-школы (доступен только из сети 21-школы).

```bash
# пути: $HOME/goinfre = /Users/<user>/goinfre
cd $HOME/goinfre
git clone <repository-url> ai-seller
cd ai-seller/ai_seller
```

**0. Инструменты — всё в `goinfre`:**
```bash
# Homebrew в goinfre (префикс $HOME/goinfre/.brew), затем:
$HOME/goinfre/.brew/bin/brew install ollama

# Miniforge в goinfre: скачать installer с https://github.com/conda-forge/miniforge/releases
bash Miniforge3-MacOSX-x86_64.sh -p $HOME/goinfre/miniforge3
$HOME/goinfre/miniforge3/bin/conda create -n python311 python=3.11 -y
export PATH=$HOME/goinfre/miniforge3/envs/python311/bin:$PATH

# Qdrant: бинарник в $HOME/goinfre/qdrant (см. https://github.com/qdrant/qdrant/releases)
```

**1. Окружение и зависимости:**
```bash
cp .env.example .env        # затем впишите свой OPENAI_API_KEY (ключ 21-школы) — НЕ коммитьте .env!
export PYTHONPATH=$PWD
pip install -e .
```

**2. Qdrant** (родной бинарник, без Docker — API на http://localhost:6333):
```bash
cd $HOME/goinfre/qdrant && ./qdrant &
```

**3. Таблицы + каталог** (Postgres не нужен — конфиг использует SQLite `/tmp/ai_live.db`):
```bash
alembic upgrade head
python scripts/import_catalog_db.py     # импортирует rag/knowledge/compatibility/catalog_orion_price_filled.csv
```

**4. RAG-индексы (коллекции Qdrant):**
```bash
# сейлз-диалоги (jsonl) -> sales_knowledge:
python -m rag.embeddings.build_index
# база знаний rag/knowledge/... -> product_knowledge:
python -m rag.embeddings.build_knowledge_index
```

**5. LLM — OpenAI-совместимый GigaChat 21-школы** (уже стоит в `.env.example`):
```bash
# .env:
#   LLM_PROVIDER=openai
#   LLM_PRIMARY=openai
#   LLM_FALLBACK=ollama
#   OPENAI_BASE_URL=https://gigachat-students.nsk.21-school.ru/v1
#   OPENAI_API_KEY=sk-...            # реальный ключ, выданный школой
#   OPENAI_MODEL=Gigashlep/GigaChat-2-Max
```
Это обычный OpenAI-совместимый `/v1/chat/completions`; провайдер `openai` в
`app/ai/llm/manager.py` умеет любой такой API.

**6. Ollama — локальный fallback/офлайн-режим** (если сеть школы недоступна):
```bash
ollama serve &
ollama pull llama3.2:latest
# если нет доступа к school-серверу, в .env переключите primary на ollama:
#   LLM_PROVIDER=ollama  LLM_PRIMARY=ollama  LLM_FALLBACK=openai
# (необязательно, чтобы модели не раздували домашнюю квоту:)
# export OLLAMA_MODELS=$HOME/goinfre/ollama
```

**7. Проверка стека и запуск:**
```bash
python scripts/check_stack.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
# виджет: http://localhost:8000/widget/demo.html
# диагностика LLM:  curl http://localhost:8000/api/v1/diagnostics/llm
# диагностика RAG:  curl http://localhost:8000/api/v1/diagnostics/rag
```

## 📚 Структура проекта

```
ai_seller/
├── app/                          # Основное приложение
│   ├── api/                      # API маршруты и зависимости
│   │   ├── routes/               # Маршруты API
│   │   └── dependencies.py      # Зависимости FastAPI
│   ├── application/             # Прикладной слой
│   │   ├── services/            # Бизнес-сервисы
│   │   ├── use_cases/           # Сценарии использования
│   │   └── dto/                # DTO объекты
│   ├── domain/                  # Доменный слой
│   │   ├── customer/           # Сущности клиента
│   │   ├── conversation/       # Сущности диалога
│   │   ├── product/           # Сущности товара
│   │   ├── order/             # Сущности заказа
│   │   ├── sales/             # Сущности продаж
│   │   └── shared/            # Общие сущности
│   ├── infrastructure/         # Инфраструктурный слой
│   │   ├── database/           # База данных
│   │   ├── redis/             # Redis
│   │   ├── qdrant/            # Qdrant
│   │   ├── llm/               # LLM провайдеры
│   │   ├── telegram/          # Telegram
│   │   └── website/           # Веб-сайт
│   ├── ai/                     # AI компоненты
│   │   ├── agent/             # AI агент
│   │   ├── rag/               # RAG
│   │   ├── memory/            # Память
│   │   ├── prompts/           # Промпты
│   │   └── tools/             # Инструменты
│   └── core/                   # Ядро приложения
│       ├── config.py           # Конфигурация
│       ├── logging.py          # Логирование
│       └── security.py         # Безопасность
├── rag/                        # RAG данные
│   ├── knowledge/              # База знаний
│   ├── seller_dialogues/       # Диалоги продавца
│   └── embeddings/            # Индексация
├── widget/                     # Веб-виджет
│   ├── src/                   # Исходники
│   └── dist/                  # Сборка
├── migrations/                 # Миграции базы данных
├── tests/                     # Тесты
├── scripts/                   # Скрипты
├── docker/                    # Docker конфигурации
├── nginx/                     # Nginx конфигурации
├── pyproject.toml             # Зависимости
├── docker-compose.yml         # Docker Compose
├── .env.example               # Пример конфигурации
└── README.md                  # Документация
```

## 🎯 Возможности

### Каналы общения
- ✅ **Telegram бот** - полноценный чат в Telegram
- ✅ **Веб-виджет** - встраиваемый чат для сайта
- ✅ **REST API** - для интеграции с другими системами
- 🚧 **WebSocket** - для потоковой передачи сообщений

### AI Возможности
- ✅ **Мультимодальные LLM** - поддержка GigaChat, Ollama, OpenAI
- ✅ **RAG (Retrieval-Augmented Generation)** - поиск по базе знаний
- ✅ **Sales RAG** - специализированная база диалогов продаж
- ✅ **Память диалога** - запоминание контекста разговора
- ✅ **Обработка возражений** - работа с ценовыми и другими возражениями
- ✅ **Рекомендации товаров** - подбор подходящих линз

### Бизнес-функции
- ✅ **Каталог товаров** - управление ассортиментом
- ✅ **Совместимость** - проверка совместимости с автомобилями
- ✅ **Управление заказами** - оформление и отслеживание заказов
- ✅ **CRM интеграция** - работа с лидами и клиентами
- ✅ **Аналитика** - сбор статистики и метрик

## 🔧 Конфигурация

### Основные параметры

| Параметр | Описание | Значение по умолчанию |
|----------|----------|----------------------|
| `LLM_PROVIDER` | Провайдер LLM (`ollama`/`gigachat`/`openai`/...) | `openai` |
| `OPENAI_BASE_URL` | OpenAI-совместимый URL (напр. GigaChat 21-школы) | - |
| `OPENAI_API_KEY` | Ключ OpenAI-совместимого API (`sk-...`) | - |
| `OPENAI_MODEL` | Модель OpenAI-совместимого API | `Gigashlep/GigaChat-2-Max` |
| `OLLAMA_BASE_URL` | URL Ollama | `http://localhost:11434` |
| `OLLAMA_DEFAULT_MODEL` | Модель Ollama | `llama3.2:3b` |
| `GIGACHAT_API_KEY` | API ключ публичного GigaChat (geo-restricted) | - |
| `DATABASE_URL` | URL базы данных | `postgresql+asyncpg://...` |
| `REDIS_URL` | URL Redis | `redis://localhost:6379/0` |
| `QDRANT_URL` | URL Qdrant | `http://localhost:6333` |

### Пример конфигурации для производства

```bash
# .env
APP_ENV=production
DEBUG=false
SECRET_KEY=your-very-secret-key

DATABASE_URL=postgresql+asyncpg://user:password@db:5432/ai_seller
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333

LLM_PROVIDER=gigachat
GIGACHAT_API_KEY=your-gigachat-api-key
OLLAMA_BASE_URL=http://ollama:11434

TELEGRAM_BOT_TOKEN=your-telegram-bot-token
WIDGET_API_KEY=your-widget-api-key

LOG_LEVEL=INFO
LOG_FORMAT=json
```

## 📊 Архитектура

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        КЛИЕНТЫ                                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  Telegram   │    │   Website   │    │    API      │    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    │
└─────────┼─────────────────┼─────────────────┼────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACE LAYER                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  Telegram Adapter│  │  Website Adapter │  │ REST API    │  │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘  │
└───────────┼──────────────────┼──────────────────┼────────────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    SellerAgent                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │  │
│  │  │  Intent     │  │  Context    │  │  Sales Strategy  │  │  │
│  │  │  Detection  │  │  Builder    │  │  & State Machine │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐    │
│  │   RAG Engine    │  │  Memory Service  │  │  Product    │    │
│  │                 │  │                 │  │  Service    │    │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘    │
└───────────┼──────────────────┼──────────────────┼────────────┘
            │                  │                  │
            ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE LAYER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │ PostgreSQL  │  │    Redis    │  │   Qdrant    │  │  LLM    │  │
│  │             │  │             │  │             │  │ Gateway │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Поток обработки сообщения

```
Customer Message
       │
       ▼
┌─────────────────┐
│   Adapter       │  (Telegram/Web/API)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   MessageInput  │  (DTO)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SellerAgent     │
│  │
│  ├─ Intent Detection
│  ├─ Context Building
│  ├─ RAG Retrieval
│  ├─ Product Search
│  ├─ Prompt Building
│  └─ Response Generation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AgentResponse  │  (DTO)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Adapter       │  (Telegram/Web/API)
└────────┬────────┘
         │
         ▼
    Customer
```

## 🛠️ Разработка

### Запуск тестов

```bash
# Все тесты
pytest

# С отчётом о покрытии
pytest --cov=app --cov-report=html

# Только unit-тесты
pytest tests/unit

# Только интеграционные тесты
pytest tests/integration
```

### Линтинг и форматирование

```bash
# Форматирование кода
black app tests

# Линтинг
ruff check app tests

# Автоисправление
ruff check --fix app tests

# Типизация
mypy app
```

### Работа с базой данных

```bash
# Создать миграцию
alembic revision auto -m "add_new_feature"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

### Индексация RAG данных

```bash
# Индексация Sales RAG
python rag/embeddings/build_index.py

# Тестирование поиска
python -c "
from rag.embeddings.build_index import SalesRAGIndexer
import asyncio

async def test():
    indexer = SalesRAGIndexer()
    results = await indexer.search_similar('Клиент говорит что дорого', limit=3)
    for r in results:
        print(r)

asyncio.run(test())
"
```

## 📦 API Документация

После запуска приложения, документация API доступна по адресам:
- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`
- **OpenAPI JSON**: `http://localhost:8000/api/openapi.json`

### Основные эндпоинты

#### Конверсации
- `POST /api/v1/conversations` - Создать новую конверсацию
- `GET /api/v1/conversations` - Список конверсаций
- `GET /api/v1/conversations/{id}` - Получение конверсации

#### Сообщения
- `POST /api/v1/conversations/{id}/messages` - Отправить сообщение
- `GET /api/v1/conversations/{id}/messages` - История сообщений

#### Товары
- `GET /api/v1/products` - Список товаров
- `GET /api/v1/products/{id}` - Получение товара
- `GET /api/v1/products/{id}/compatibility` - Проверка совместимости

#### Рекомендации
- `POST /api/v1/recommendations` - Получить рекомендации

#### Telegram
- `POST /api/v1/telegram/webhook` - Webhook для Telegram

## 🚀 Деплой

### Docker Compose (для разработки)

```bash
# Запуск всех сервисов
docker-compose up -d

# Остановка
docker-compose down

# Просмотр логов
docker-compose logs -f api
```

### Production Deployment

1. **Соберите Docker образ**:
```bash
docker build -t ai-seller -f docker/Dockerfile .
```

2. **Запустите с Docker Compose для production**:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

3. **Настройте Nginx** (опционально):
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --profile production up -d
```

## 📊 Мониторинг

### Логи
- Логи приложения доступны в stdout контейнера
- Для production рекомендуется настроить внешнюю систему логирования (ELK, Loki, etc.)

### Метрики
- Планируется интеграция с Prometheus и Grafana

### Здоровье системы
- `GET /health` - базовая проверка здоровья
- `GET /api/v1/health/detailed` - детальная проверка всех компонентов

## 🤖 AI Модели

### Поддерживаемые провайдеры
- **Ollama** - локальные модели (рекомендуется для разработки)
- **GigaChat** - Sberbank GigaChat (рекомендуется для производства в РФ)
- **OpenAI** - планируется
- **Anthropic Claude** - планируется

### Рекомендуемые модели

#### Для Ollama
- `llama3.2:3b` - быстрая, подходит для тестирования
- `llama3.2:8b` - более качественная, для production
- `mistral:7b` - хорошее качество генерации

#### Для GigaChat
- `GigaChat` - основная модель
- `GigaChat-Pro` - расширенная модель

### Настройка embedding моделей
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` - мультиязычная модель
- `BAAI/bge-small-en-v1.5` - английская модель
- `intfloat/multilingual-e5-small` - мультиязычная модель

## 📝 Лицензия

MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 🙏 Вклад

Вклады приветствуются! Пожалуйста, следуйте этим шагам:

1. Форкните репозиторий
2. Создайте ветку для вашей функции (`git checkout -b feature/amazing-feature`)
3. Закоммитьте изменения (`git commit -m 'Add amazing feature'`)
4. Запушьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📞 Контакты

- **Email**: your.email@example.com
- **Telegram**: @your_telegram
- **Website**: https://your-website.com

---

Сделано с ❤️ для автомобильной индустрии
