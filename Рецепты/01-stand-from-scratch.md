# Развернуть стенд с нуля

> [!info] Рецепт — живая инструкция
> Поддерживается в актуальном состоянии, в отличие от лаб. Отвечает
> на «как сделать», а не «как устроено»: устройство стенда и обоснования —
> [08-local-stand.md](../08-local-stand.md), замеры — там же.

Занимает около получаса, из них 25 минут — скачивание моделей.
Прав администратора и Docker не нужно.

### 1. Инструменты

```bash
brew install llama.cpp uv
```

### 2. Папка стенда — вне iCloud и вне репозитория волта

```bash
mkdir -p ~/Development/Home/RAG-stand/{bin,storage,models,snapshots,logs}
```

`~/Development` не синхронизируется с iCloud — в отличие от `Desktop` и `Documents`, которые на этой машине синхронизируются (проверено). Подробнее — [[08-local-stand#Гигиена данных|гигиена данных]].

Стенд — **отдельный репозиторий**, а не часть волта: [[08-local-stand#Стенд под собственным гитом|почему так]].

### 3. Qdrant

```bash
curl -sL -o /tmp/qdrant.tar.gz https://github.com/qdrant/qdrant/releases/download/v1.19.0/qdrant-aarch64-apple-darwin.tar.gz
```

```bash
shasum -a 256 /tmp/qdrant.tar.gz
```

Ожидаемая сумма: `4e279a80cc1ebe73e859318ff86375af54c123887dd7ae46605c0eb6cb7c44e8`

```bash
tar xzf /tmp/qdrant.tar.gz -C ~/Development/Home/RAG-stand/bin && chmod +x ~/Development/Home/RAG-stand/bin/qdrant
```

Бинарник подписан ad-hoc (linker-signed), Gatekeeper его пропускает; карантина нет, потому что скачан через `curl`, а не браузером.

### 4. Веб-дашборд

```bash
curl -sL -o /tmp/qdrant-ui.zip https://github.com/qdrant/qdrant-web-ui/releases/download/v0.2.16/dist-qdrant.zip
```

Сумма: `4446f0cea024078011c78cd24a592c9b563656d15205818563fa6b22d394dd29`

```bash
unzip -q /tmp/qdrant-ui.zip -d /tmp/qdrant-ui && mv /tmp/qdrant-ui/dist ~/Development/Home/RAG-stand/static
```

### 5. Конфигурация и ключи

Файл `.env` в папке стенда, права 600, ключи случайные:

```bash
cd ~/Development/Home/RAG-stand && umask 077 && printf 'QDRANT_URL=http://127.0.0.1:6333\nEMBEDDER_URL=http://127.0.0.1:8080\nRERANKER_URL=http://127.0.0.1:8081\nQDRANT_API_KEY=%s\nLLAMA_API_KEY=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" > .env
```

`.env` — единственное место с адресами. Переезд на инфраструктуру партнёра = правка этого файла, а не кода.

### 6. Скрипты запуска

В папке стенда лежат `run-qdrant.sh`, `run-embedder.sh`, `run-reranker.sh` и обёртки `start-stand.sh` / `stop-stand.sh` / `check-stand.sh`. Вся конфигурация — внутри них, с комментариями «почему именно так». Ключевые параметры разобраны в [[08-local-stand#Ключевые параметры и почему они такие|справочнике стенда]].

```bash
cd ~/Development/Home/RAG-stand && ./start-stand.sh && ./check-stand.sh
```

Первый запуск скачает обе модели (1,2 ГБ) — это долгая часть. Дальше `-hf` берёт их из кэша в `models/`.

## Проверка — до всякого кода

`./check-stand.sh` выполняет четыре проверки. Пять минут, экономят часы отладки.

| # | Проверка | Что ловит |
|---|---|---|
| 1 | Сервисы отвечают | Не поднялось / порт занят |
| 2 | Без ключа — 401, из сети — недоступен | Ошибку конфигурации безопасности |
| 3 | Размерность + косинус на трёх текстах | Неверный pooling, забытые префиксы, неподходящую модель |
| 4 | Реранкер различает документы | Битую конвертацию GGUF |
| 5 | `/props` + тексты растущей длины | Расхождение скрипта запуска с реальностью; недостаточный контекст |

Третья проверка устроена так: два текста про одно и то же **разными словами** («неустойка 0,1% за просрочку доставки» и «пеня одна десятая процента в сутки за задержку») и один про другое (санитарное состояние помещения). Разные слова принципиальны — на одинаковых проверка выродилась бы в сравнение подстрок.

