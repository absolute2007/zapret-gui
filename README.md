# Zapret GUI v2.0

Графический интерфейс для утилиты [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

**Автор:** [absolute2007](https://github.com/absolute2007)

![Zapret GUI](https://img.shields.io/badge/version-2.0-blue) ![Windows](https://img.shields.io/badge/platform-Windows-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

<img width="550" height="375" alt="изображение" src="https://github.com/user-attachments/assets/e2501d34-10fa-43d1-90dd-6e190228b36b" />


## Возможности

- **Управление списками** — редактирование list-general.txt и других файлов
- **Импорт доменов** — слияние внешних списков с основным
- **Запуск стратегий** — выбор и запуск general*.bat файлов
- **Автозапуск** — установка как службы Windows
- **Game Filter** — расширенный диапазон портов для игр
- **IPset** — переключение режимов IP-фильтрации
- **Discord Hosts** — обновление hosts для голосовых серверов
- **Проверка доступности** — тест DNS и HTTPS соединения
- **Мониторинг** — статус winws.exe, службы zapret, драйвера WinDivert
- **Темы** — светлая и тёмная тема (Fluent Design)
- **Сброс настроек** — полная переустановка Zapret

## Установка

### Готовый установщик (рекомендуется)

1. Скачайте `ZapretGUI_Setup.exe` из [Releases](https://github.com/absolute2007/zapret-gui/releases)
2. Запустите установщик
3. Программа установится в `%USERPROFILE%\zapret-gui` и создаст ярлык на рабочем столе
4. При первом запуске автоматически скачается утилита Zapret

### Структура папок после установки

```
%USERPROFILE%\zapret-gui\
├── app\               # Файлы приложения
│   ├── ZapretGUI.exe
│   └── _internal\
└── zapret\            # Zapret (скачивается автоматически)
    ├── bin\
    ├── lists\
    └── service.bat
```

### Из исходников

```bash
cd src
pip install -r requirements.txt
python main.py
```

### Сборка установщика

```bash
cd src
build.bat
```

Результат: `src\release\ZapretGUI_Setup.exe`

## Требования

- Windows 10/11
- Права администратора (для управления службами)

## Важно

- Для работы стратегий и установки службы требуются **права администратора**
- При запуске приложения без прав администратора будет запрошено повышение привилегий
- Служба Zapret запускается автоматически при старте Windows

## Changelog

### v2.0
- Новый дизайн на основе Fluent Design (PyQt6 + QFluentWidgets)
- Улучшенный установщик
- Установка в домашнюю директорию пользователя
- Исправлены проблемы со сборкой

### v1.0
- Первая версия (тестовая)

## Лицензия

MIT
