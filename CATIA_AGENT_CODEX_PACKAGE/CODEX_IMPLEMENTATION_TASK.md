# Задание Codex на расширение API агента CATIA V5

Расширь существующий CATIA V5 MCP server по прилагаемой спецификации. Сначала прочитай AGENTS.md репозитория, CATIA_AGENT_IMPLEMENTATION_SPEC.md, CATIA_AGENT_TOOL_CATALOG.json, CATIA_AGENT_API_SYMBOLS.json и CATIA_AGENT_ENUMS.json. Сохрани существующий transport, правила доступа и рабочие tools.

Большие JSON изучай выборочно: загрузить программно, извлечь нужные capability IDs и resolved_symbol для текущего этапа. Не выводи весь словарь из 1529 символов в один ответ или контекст. Для первичного перечня используй CSV-индекс.

## Сначала исследование проекта

Проверь git status, регистрацию tools, backend соединения, текущие schemas и тесты. Сопоставь существующие handlers с capability IDs. Статический файл CATIA_AGENT_EXISTING_TOOLS.json — ориентир из предыдущего checkout; актуальный код имеет приоритет. Не дублируй существующие функции и не объявляй статически найденный handler работающим без теста.

Составь конкретную implementation matrix: capability, existing handler, missing behavior, backend call, test. Прямой pywin32 COM backend можно сохранить. Pycatia methods и COM methods имеют разные conventions, особенно для output arrays; проверяй оба поля каталога.

## Реализация по этапам

Сначала проверь P0: один COM worker, document binding, Reference resolver, явные units, ошибки и политика частично выполненных запросов. Затем реализуй отсутствующие P1 capabilities. Продолжай к P2 и P3, сохраняя небольшой проверяемый шаг и совместимость публичных контрактов.

У каждого нового tool должны быть конкретная JSON Schema, проверка геометрических типов, явное назначение container, обработка Update и постусловия. После каждой завершённой группы запускай релевантные offline tests. На доступном Windows CATIA host запускай геометрические integration tests. Если такого host нет, продолжай полезную offline реализацию и помечай live verification как не выполненную.

Не генерируй 218 однотипных wrappers автоматически по названию GUI-команды. Используй parameterized handlers для Hole, limits, planes и constraints. Каждый property setter должен действительно существовать; readonly property, содержащая изменяемый объект, не становится setter.

## Требования к сложным случаям

Solid Loft: generic AnyObject → Loft → HybridShapeLoft; параметры сечений задаются на HybridShapeLoft. Product.constraints() в Python соответствует COM Connections("CATIAConstraints"). Rule создаётся через Relations.create_program. Point On Surface не имеет универсального аргумента uv. У Sketch нет подтверждённого support setter, а у DraftDomains нет add.

Для unconfirmed capabilities не придумывай вызов. Реализуй корректный unsupported response и отдельную запись исследовательской задачи. Composite tools ограничь поддержанными типами геометрии. Geometry-equivalent fallback не выдавай за тождественное GUI feature.

Произвольные команды и скрипты из LLM не должны обходить typed tools. Сохранение, экспорт, закрытие и overwrite должны следовать действующим правилам проекта и явным параметрам запроса. Не выполнять push, deployment или destructive cleanup без отдельного указания пользователя.

## Отчёт о результате

Для каждой изменённой capability укажи файлы, поддержанные входы, точный backend API, выполненные tests, ограничения и Windows CATIA verification status. Разделяй documented, implemented, offline_tested и live_tested. Покажи нерешённые API gaps и не объявляй проект полностью готовым только потому, что тесты с mocks прошли.
