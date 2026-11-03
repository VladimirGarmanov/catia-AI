# Проверка проекта 0.2.1 — 2026-11-02

Проверка выполнена на macOS / Python 3.12. Проверены исходники общих путей
выполнения, схемы всех инструментов, существующий offline-набор, зависимости,
сборка Python-пакета и Windows launch/update/build scripts. Это **не проверка
каждого COM-вызова на CATIA** и не подтверждение всех режимов GUI.

## Результат

| Проверка | Результат |
| --- | --- |
| Полный pytest до исправлений | 196 passed, 8 failed, 1 skipped |
| Полный pytest после исправлений | 213 passed, 1 skipped |
| Пропущенный тест | Реальная обработка кавычек cmd.exe; нужен Windows |
| Все 22 группы / 147 MCP-инструментов | Импорт, регистрация, уникальность, схемы PASS |
| Исходные 81 имени инструментов | Сохранены |
| Реальный stdio discovery | 147 full / 13 inspection, PASS; без CATIA-вызовов |
| Установка `.[dev,drawings]` и pip check | PASS на Mac, pywin32 не требуется |
| Ruff F/E9 | PASS для сервера, scripts и tests |
| Wheel 0.2.1 | Собран, все 33 Python-модуля и API-каталог присутствуют |
| Windows EXE, клиенты и геометрия CATIA | Локально НЕ запускались |

Полный набор включает контракты sketch/constraints, Part Design/patterns,
GSD/advanced operations, Assembly/Drawing, selection/context, rename, desktop
fallback, session/replay, client launchers и PDF/image preparation. Покрытие
не означает, что каждая комбинация аргументов или каждая фича проверена.

## Исправлено

1. Общие схемы режимов больше не перезаписывают ограничения одноимённых полей.
   Например, signed distance для point-on-surface не наследует positive-only
   tolerance из healing. Каждая ветка теперь проверяет собственные поля.
2. Ошибки подключения, отсутствия документа и неверного типа передают
   машинно читаемые коды. Ошибка чтения ActiveDocument при наличии документа
   больше не выдаётся за отсутствие документа.
3. Сообщения об отсутствии exact edge enumeration / bounding box доступны
   без попытки запустить CATIA. Старые edge/face-name аргументы отклоняются
   до изменения InWorkObject.
4. Bundled Codex/Claude запускают `scripts/mcp_entry.py`: MCP импортируется
   из обновлённого проекта, а не из старой копии в embedded site-packages.
   Исправлен также `python313._pth` новых EXE. INSTALL использует уже имеющийся
   bundled Python вместо ненужной загрузки ещё одного Python.
5. UPDATE сохраняет настройки обоих клиентов, `.env*` и CAD/чертежи во всех
   подпапках; отвергает некорректные архивные пути и linked targets. Неизменённые
   файлы не переписываются. При ошибке копирования восстанавливаются заменённые
   файлы. Старые/лишние файлы автоматически не удаляются.
   Node installer и UPDATE проверяют raw ZIP member names: Windows-normalization
   в ZipInfo.filename не скрывает обратные слеши от проверки.
6. Ошибка установки зависимостей теперь завершает UPDATE ненулевым кодом.
   Новые файлы остаются, поскольку pip не транзакционный; `.local/dependencies-pending`
   обеспечивает повтор этой стадии при следующем запуске. Успешный INSTALL
   снимает этот маркер для source `.venv`.
7. requirements.txt согласован с pyproject: jsonschema, Windows Pillow/pywin32,
   Python 3.10 tomli; MCP >=1.30 — проверенная в этой среде версия. Python-пакет
   и версия Inno Setup обновлены до 0.2.1. Node/Codex/Claude на Windows этим
   Mac-аудитом не обновлялись; их фактические версии проверяет DIAGNOSE.
8. Логи MCP идут в stderr без обязательной записи в каталог установленного
   пакета. Исправлены устаревшие тесты, неиспользуемые imports/variables.
   Offline-тесты отключают реальный COM даже на Windows; тест COM-подключения
   явно заменяет pywin32 двойниками. CI дополнен lint/pip check/registration.
   Windows builder проверяет импорт DLL pywin32, источник catia_mcp и stdio
   discovery именно встроенным Python до упаковки EXE, без подключения к CATIA.
   Для GitHub release metadata builder использует read-only workflow token,
   чтобы общий IP hosted runner не упирался в anonymous API rate limit.

## Upgrading

Закрой AI-клиента перед обновлением. Для существующей **source ZIP** копии:

```powershell
.\UPDATE.cmd
.\INSTALL.cmd
.\START_AI.cmd
```

Старый UPDATE специально **не обновлял свой файл** `scripts/update_project.py`.
Он доставит остальной код 0.2.1, но для получения исправлений самого обновлятора
один раз скопируй `scripts/update_project.py` из свежего GitHub ZIP в ту же
подпапку существующего проекта. `.venv`, `.local`, настройки и модели переносить
или удалять не нужно. Новая версия уже обновляет собственный Python-файл;
исполняемый в этот момент UPDATE.cmd сохраняется.

Для **полного EXE** при изменении зависимостей установи свежий Windows installer
поверх старого. UPDATE не обещает обновить embedded Python или сторонние CLI.
Новый transport bootstrap также работает со старым embedded Python, если его
зависимости совместимы. Не считай ненулевой update exit code завершённой установкой.

## Что осталось проверить на Windows

- Чистую установку ZIP без Python/Node/Git и установку EXE без admin; пути с
  пробелами/Unicode, ограничения университетского компьютера без их обхода.
- UPDATE из предыдущей версии, сохранность локальных настроек, повтор после
  сетевой ошибки, запуск обновлённого source MCP из старого/нового EXE.
- В собственной сессии Codex и отдельно Claude: все 147 tools видны и callable;
  вход в аккаунты и доступность моделей не проверяются Python-тестами.
- На новой несохранённой детали: sketch → geometric/dimensional constraints →
  close → pad → pocket → update → readback; затем [patterns](PATTERNS.md).
- Exact selected face/edge → fillet/chamfer/shell; Shaft/Groove со sketch axis;
  native Sketch Analysis для утверждения fully constrained.
- [Assembly/Drawing сценарии](ASSEMBLY_DRAWING.md), SAFEARRAY, единицы и
  placement; [переименование](NAMING.md) с открытым sketch.
- Ошибку Update, stale handles и COM busy/timeout без дублирования записи;
  screenshot/image delivery и согласованный UI fallback на том же Windows host.

Никакие пользовательские CATPart/CATProduct/CATDrawing в ходе этого аудита
не открывались и не изменялись. Глобальные настройки Codex/Claude не переписывались.
