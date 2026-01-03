# Zapret GUI v1

Графический интерфейс для утилиты [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube).

**Автор:** [absolute2007](https://github.com/absolute2007)

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
- **Темы** — светлая и тёмная тема интерфейса
- **Сброс настроек** — полная переустановка Zapret

## Установка

### Готовый EXE (рекомендуется)
1. Скачайте `ZapretGUI.exe` из [Releases](https://github.com/absolute2007/zapret-gui/releases)
2. Запустите файл
3. Программа автоматически скачает утилиту Zapret и создаст ярлык на рабочем столе

Установка производится в: `%USERPROFILE%\zapret-gui`

### Из исходников
```bash
cd src
pip install -r requirements.txt
python main.py
```

### Сборка EXE
```bash
cd src
build.bat
```
Готовый файл: `src\dist\ZapretGUI.exe`

## Важно

- Для работы стратегий и установки службы требуются **права администратора**
- Служба запускается автоматически при старте Windows

## Лицензия

MIT
