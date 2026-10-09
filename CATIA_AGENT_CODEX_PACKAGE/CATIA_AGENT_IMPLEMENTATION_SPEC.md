# Спецификация API инструментов CATIA V5 для реализации AI агента

Этот пакет предназначен для Codex, который расширяет CATIA MCP server. Задача — реализовать проверяемые операции моделирования через CATIA Automation, используя точные методы, свойства и типы pycatia. Все 218 позиций предыдущего справочника сопоставлены с API либо явно отмечены как составные, частично покрытые или не подтверждённые. Это спецификация реализации, а не готовая реализация сервера.

Базовая документация: [pycatia API](https://pycatia.readthedocs.io/en/latest/api_index.html), версия сайта при проверке **0.10.1**, дата проверки **8 октября 2026**. Для страниц, массовую загрузку которых сайт ограничил, сигнатуры сверены с исходниками официального пакета **pycatia 0.10.1**. Источник каждого символа указан в JSON. Проверка документации и Python-исходников не заменяет испытания на лицензированном Windows CATIA V5.

## Как передать пакет Codex

Прочитать этот документ, затем `CATIA_AGENT_TOOL_CATALOG.json`, `CATIA_AGENT_API_SYMBOLS.json` и `CATIA_AGENT_ENUMS.json`. `CATIA_AGENT_API_CATALOG.md` содержит те же 218 карточек в читаемом виде. `CATIA_AGENT_TOOL_INDEX.csv` нужен для поиска и сортировки. Готовое задание находится в `CODEX_IMPLEMENTATION_TASK.md`.

У каждой карточки есть номер из предыдущего справочника, категория, способ реализации, точные API bindings, пояснение последовательности, проверки и источник. Полные сигнатуры и writable-состояние свойств находятся в словаре символов. Сигнатура не заменяет семантическую проверку аргументов: два параметра типа Reference могут означать совершенно разные геометрические объекты.

Большие JSON не нужно целиком выводить в контекст Codex. Загружать их программно, выбирать нужные capability IDs и `resolved_symbol`; возвращать только соответствующие карточки, signatures и свойства возвращаемого класса. Начинать с компактного CSV или заголовков Markdown-каталога. Так справочник можно использовать по одной группе задач без потери контекста реализации.

Имена `capability_id` — ключи спецификации. Они не означают, что в существующем сервере уже есть соответствующие MCP tools. Предложенные публичные имена можно заменить существующими совместимыми именами после проверки репозитория. Не создавать по одному новому MCP tool на каждую строку: режимы Hole, Pad и constraints следует объединять в понятные параметризованные контракты.

## Граница с существующим проектом

При подготовке просмотрен локальный `/Users/vladimir/PycharmProjects/catia-v5-mcp-server`. В `pyproject.toml` используются MCP и pywin32; pycatia не указана как зависимость. В `catia_mcp/tools/part_design.py` и `gsd.py` есть прямые COM-вызовы. Это наблюдение о текущем checkout, а не гарантия состояния Windows-установки. Репозиторий в этой задаче не изменялся.

Предпочтительный путь расширения: сохранить существующий COM backend и использовать pycatia как проверенную карту Automation API. При необходимости pycatia вводится через отдельный adapter с явной ответственностью за wrappers, enums и SAFEARRAY, после совместимых тестов. Не смешивать raw COM и pycatia objects в параметрах одной функции: wrapper обычно передаёт внутренний `.com_object` сам.

Перед правками перечитать актуальные AGENTS.md, git status, регистрацию tools и реализацию соответствующего модуля. Не заменять уже работающий обработчик только ради унификации названий. `CATIA_AGENT_EXISTING_TOOLS.json` — статический индекс найденных деклараций, а не отчёт об их работоспособности или доступности в активной сессии.

## Значение статусов

| Статус | Что реализовывать |
|---|---|
| direct | Есть конкретный documented constructor или method. Всё равно нужны разрешение ссылок, контекст и проверки. |
| property | Изменение свойств существующего feature. Нет отдельного constructor для этой кнопки/режима. |
| workflow | Несколько подтверждённых API-вызовов с явным порядком и настройкой результата. |
| composite | Собственный геометрический алгоритм из примитивов; область поддерживаемых входов должна быть ограничена контрактом. |
| partial | Подтверждена часть действия. Указать, что именно реализовано, и не выдавать это за полную эквивалентность GUI. |
| unconfirmed | Прямой API не найден в исследованном наборе. Не придумывать метод и не объявлять возможность поддержанной. |
| diagnostic | Анализ состояния и объяснение причины. Исправление — отдельная операция. |
| infrastructure | Служебный слой, не операция геометрии. |

Для runtime дополнительно хранить `documented`, `implemented`, `offline_tested`, `live_tested` и `available_in_session`. Эти признаки независимы. API может быть документирован, но отсутствовать в лицензии, не быть реализован в сервере либо не работать на выбранном типе грани.

## Архитектура обработки запроса

Последовательность одной операции:

1. Проверить schema, единицы, диапазоны, capability и разрешённую область изменения.
2. Захватить последовательный execution slot CATIA worker. Все COM-объекты принадлежат одному корректно инициализированному apartment/thread; нельзя переносить живые COM References через обычную asyncio-конкурентность.
3. Проверить document identity и текущую модель. Разрешить handles, проверить типы геометрии и occurrence context.
4. Сохранить нужный контекст: in-work object, selection и принадлежность новых объектов. Не считать это полной транзакцией.
5. Выполнить constructor, затем необходимые setters/add methods. Для sketch закрыть edition в `finally`, если открытие прошло успешно.
6. Выполнить Update нужного Part/Product/Drawing. Прочитать состояние и значения обратно.
7. Проверить измеримые постусловия. Зарегистрировать результат и вернуть структурированный ответ.
8. Если операция частично выполнилась, сообщить об этом; восстановить только те созданные объекты и контекст, восстановление которых явно поддержано и проверено.

CATIA Automation не предоставляет этому серверу автоматически атомарную транзакцию. Undo concatenation — группировка Undo, а не обещание rollback. Нельзя удалять выбранные пользователем исходные элементы при ошибке, называя это восстановлением.

Серийная очередь одного сервера не блокирует другого Automation-клиента или ручные действия пользователя. Поле `expected_revision` может быть локальным счётчиком сервера, но оно не обнаруживает все внешние правки. Перед записью перепроверять критические References и active document; после внешних изменений инвалидировать topology handles.

## Идентификация объектов

Публичный вход должен содержать `document_id` и opaque handles нужных объектов. Handle — запись реестра с session/document identity, типом и живым объектом; это не строка вроде `Edge.7` и не обещание стабильности после изменения топологии.

Предлагаемый resolver поддерживает source modes `handle`, `publication`, `selection_snapshot` и `semantic_query`. Имя feature можно использовать только с проверкой однозначности и контейнера. Для semantic query вернуть список кандидатов с измеримыми признаками; при нескольких подходящих гранях запросить выбор, не брать первую.

Для BRep не придумывать GenericNaming strings. `Part.create_reference_from_b_rep_name` принимает CATIA label и context, полученные из реальной модели. `Selection.item2(index).reference` позволяет получить выбранную точную ссылку; её нужно перечитать непосредственно перед действием. Индексы COM collections часто начинаются с 1; JSON-массивы сервера с 0. Преобразование должно быть явным.

В сборке различать definition/reference product и occurrence. Две одинаковые детали в разных местах имеют разные контексты измерения и constraints. Не разрешать ссылку только по Part Number.

## Общий контракт tools

Схемы в `CATIA_AGENT_CONTRACTS.schema.json` задают общий envelope и конкретные примеры для tangent plane, pad и измерения. Они не являются автоматически готовыми схемами всех 218 публичных tools. Остальные schemas Codex строит из сигнатур плюс семантики карточки, не публикуя необработанные COM-параметры агенту.

Общие поля для записи: `request_id`, `document_id`, `expected_revision`, `operation`, `arguments`. Удобные публичные размеры: `length_mm`, `angle_deg`, `radius_mm`. Ссылка на геометрию: handle и ожидаемый тип. Координаты должны иметь `frame_id`; массив без системы координат неоднозначен.

Ответ содержит `status` из `success`, `partial_failure`, `failed`, `unsupported`; созданные и изменённые handles; `updated`; список проверок; значения с units; warnings и error. У каждого результата измерения должно быть явно обозначено, в какой системе координат он выражен.

Минимальные ошибки: `INVALID_ARGUMENT`, `DOCUMENT_MISMATCH`, `STALE_REFERENCE`, `AMBIGUOUS_REFERENCE`, `WRONG_GEOMETRY_TYPE`, `CAPABILITY_UNAVAILABLE`, `COM_ERROR`, `UPDATE_FAILED`, `POSTCONDITION_FAILED`, `PARTIAL_MUTATION`, `UNSUPPORTED_OPERATION`.

При COM_ERROR сохранить HRESULT, EXCEPINFO и имя операции, не теряя исходную причину. Не превращать исключение в success со строкой ошибки. При таймауте COM неизвестно, завершилась ли запись: повторный request_id должен сначала согласовать состояние, иначе можно получить два Pad или две детали.

## Единицы и перечисления

`CATIA_AGENT_ENUMS.json` содержит числовые значения enum, извлечённые из официального `pycatia.enumeration.enums` версии 0.10.1. Использовать символические имена. Не заменять это предполагаемыми индексами старого `enumeration_types` tuple.

Внешний контракт сервера может использовать mm и deg, но adapter обязан задавать преобразование для каждого конкретного API. Нельзя глобально считать все float в CATIA миллиметрами или все углы градусами. Параметр дуги Factory2D, угол feature и Knowledgeware Dimension — разные контракты.

Для Knowledgeware dimensions предпочтительно `valuate_from_string("25mm")` или `valuate_from_string("30deg")`, затем чтение значения/единиц обратно. Начальные значения `create_dimension` зависят от dimension magnitude и системы единиц API; без проверки нельзя передавать публичное mm как безразмерный float.

Документация Measurable явно указывает m² для площади и m³ для объёма. Документация Inertia использует kg для массы, m для координат центра масс и kg/m³ для плотности. Момент инерции физически имеет единицы kg·m²; в старом CAA-тексте встречается неудачная запись единиц, её нельзя механически переносить в публичный контракт.

Тест единиц: куб 10 mm должен иметь объём 1000 mm³ = 1e-6 m³. При плотности 2700 kg/m³ масса 0.0027 kg. Отдельно измерить известный отрезок 10 mm и угол 90°, зафиксировав фактические единицы каждого используемого getter. Не распространять единицу Inertia COG автоматически на все координатные getters.

У `Inertia.density` есть специальные значения: при записи 0 используются плотности объектов; положительное число задаёт override. При чтении 1 означает применение default density, -1 — неоднородную плотность. Не интерпретировать -1 как физическую отрицательную плотность.

## Контекст создания геометрии

| Область | Получение объектов и завершение |
|---|---|
| Part | Documents → PartDocument → Part; выбрать Body/in_work_object; ShapeFactory; Update. |
| Sketch | Body.sketches или HybridBody.hybrid_sketches → add(plane_ref); open_edition → Factory2D; constraints; close_edition; Update. |
| GSD | Part.hybrid_shape_factory → создать feature → HybridBody.append_hybrid_shape → Update. Проверить, действительно ли factory уже вставляет конкретный объект. |
| Assembly | ProductDocument.product → Products; Product.constraints(); occurrence References; Product.update. |
| Drafting | DrawingDocument.sheets → sheet.views → DrawingView.generative_behavior; document source; define view; update. |
| Knowledgeware | Part/Product.parameters и relations; typed parameter, formula/check/design table; Update и readback. |
| Measurement | Document.get_workbench("SPAWorkbench") → get_measurable(reference); для сборки in-context варианты; вернуть units. |

Factories часто возвращают объект с минимальной настройкой. `add_new_fill()` ещё не создаёт заполненную поверхность без границ, `add_new_loft()` — законченный loft без сечений. Пустой wrapper или feature в дереве не доказывает корректную геометрию.

## Проверенные важные различия API

**Solid Loft.** `ShapeFactory.add_new_loft()` и `add_new_removed_loft()` возвращают generic AnyObject. В pycatia нужен явный wrapper `Loft(result.com_object)`, затем `HybridShapeLoft(loft.hybrid_shape.com_object)`. Сечения и guides добавляются во вложенный HybridShapeLoft. У класса Loft нет `add_section_to_loft`.

**Сборочные связи.** `Product.constraints()` — метод Python без аргументов; внутри используется raw COM `product.Connections("CATIAConstraints")`. Не создавать вымышленный `product.connections()` в pycatia. В raw COM передавать строку обязательно.

**Shaft и Revol.** Shaft создаёт solid из эскиза, ось задаётся через `Revolution.revolute_axis`. `HybridShapeFactory.add_new_revol(profile, begin_angle, end_angle, axis)` создаёт поверхность и принимает другой набор аргументов. Подмена одного другим неверна.

**Draft.** `ShapeFactory.add_new_draft` уже принимает первую грань, neutral/parting References, направление, угол и режимы. `DraftDomains` имеет `item`, но не `add`. Дополнительные грани назначаются на полученном DraftDomain.

**Radius и Diameter в Sketcher.** В `CatConstraintType` есть `catCstTypeRadius`; отдельного diameter enum в этой версии нет. Для управляющего диаметра можно использовать параметр D и формулу R = D/2. Это не обещает автоматически нужный вид размерной надписи в GUI.

**Rule.** В `Relations` нет `create_rule`; `create_program(name, comment, program_body)` возвращает Rule. Проверять Knowledgeware syntax и лицензию.

**SAFEARRAY.** Python-метод может возвращать tuple, тогда как COM заполняет выходной массив. Иногда pycatia применяет внутренний VBA bridge. Поля `com_signature_from_help`, `python_signature` и `uses_vba_bridge` показывают, где нужен отдельный adapter. Не копировать Python-сигнатуру буквально в прямой COM-вызов.

**Нет универсального центра поверхности.** `add_new_point_on_surface` принимает surface, direction и scalar distance. Для заданного центра верхней грани нужно сначала формализовать центр через конструктивные плоскости/координаты/проекцию, получить точку и только затем tangent plane.

## Приоритет реализации

| Этап | Состав | Критерий готовности |
|---|---|---|
| P0 | session, document binding, model state, selection snapshot, resolver, typed errors, serial worker, units | Нельзя изменить другой документ или повторить неопределённую запись без согласования состояния. |
| P1 | Sketch primitives, constraints, Pad/Pocket/Hole, points/lines/planes, Update, measurements | На Windows создаётся параметрическая контрольная деталь; размеры прочитаны назад и проверены. |
| P2 | Shaft/Groove, Rib/Slot/Stiffener, lofts, fillet/chamfer/shell/draft, patterns, booleans | Каждая операция имеет положительный и геометрически некорректный тест; после ошибки известны созданные объекты. |
| P3 | GSD surfaces, assemblies, drafting, materials, exports, parameters/formulas | Проверены associativity, assembly context, drawing links и повторный импорт экспортов. |
| P4 | composites in Sketcher, templates, kinematics, неподтверждённые UI operations | Каждая возможность отдельно исследована и испытана; неподдержанные случаи возвращают unsupported. |

Нумерация карточек не задаёт порядок разработки. Начать с инфраструктуры и 15–25 необходимых публичных tools, затем добавлять capabilities к существующим handlers. Контекстное меню и дерево модели не заменять общим `execute_python` или `start_command` как обходным путём.

## Как реализовать составные операции

Sketcher Rectangle — четыре примитива и constraints. Sketcher Mirror — отражение поддержанных типов плюс ассоциативные связи, если они обещаны контрактом. Trim/Break/Offset требуют вычисления пересечений, выбора интервала и восстановления зависимостей; первая версия может поддерживать только линии и окружности. Для spline возвращать unsupported до появления отдельного алгоритма.

Multi Pad/Multi Pocket не найдены как прямые methods ShapeFactory. Несколько обычных Pad/Pocket могут решать геометрическую задачу, но создают другое дерево. Такой алгоритм должен иметь другое имя и явно описанный результат.

Sheet Metal Wall, Bend, Hem и ряд других GUI commands не подтверждены в просмотренном pycatia API. Не делать вывод о наличии этих constructors из названия `smt_interfaces`: этот пакет содержит инструменты DMU Optimizer, а не универсальный sheet-metal factory. Возможный путь — проверенный CATPart/PowerCopy template с опубликованными входами. Создание такого template и подтверждение unfoldability — отдельная работа.

Если требуется GUI-only fallback, держать его отдельной capability с явным modal state и ограниченным сценарием. Он не является прямым API и не может наследовать статус live_tested обычного COM tool. В существующем проекте соблюдать запреты AGENTS.md на обход разрешённого MCP transport.

## Минимальные обязательные проверки

### Контракт создания касательной плоскости

Связанные карточки: CATIA-108, CATIA-092 и CATIA-126. Surface и Point разрешаются в реальные геометрические References одного Part. Container — целевой HybridBody. Проверить принадлежность точки поверхности с согласованным допуском; если способ измерения для данной пары типов недоступен, не утверждать успешность этой проверки. Положение точки «по центру» не определяется этим tool.

Последовательность backend: `Part.create_reference_from_object(surface)` и `Part.create_reference_from_object(point)` для допустимых целых features либо реальный BRep Reference от resolver; затем `HybridShapeFactory.add_new_plane_tangent(surface_ref, point_ref)`; `HybridBody.append_hybrid_shape(plane)`; присвоить имя; `Part.update_object(plane)`. Вернуть handle плоскости и результаты проверки. Смена названия не должна становиться её единственным идентификатором.

| Публичный аргумент | Binding |
|---|---|
| surface_handle | resolver → i_surface: Reference |
| point_handle | resolver → i_pt: Reference |
| container_handle | receiver для append_hybrid_shape |
| point_on_surface_tolerance_mm | геометрическая проверка сервера; в constructor не передаётся |
| name | AnyObject.name после создания |

Postconditions: объект типа plane, находится в заданном контейнере, актуален после Update, проходит через заданную точку и имеет нормаль, согласованную с локальной нормалью поверхности. Проверки, которые adapter не умеет выполнить, возвращать как непроверенные, а не passed.

### Контракт создания Pad

Связанные карточки CATIA-046 и CATIA-058–063. До constructor разрешить Sketch и target Body, убедиться, что edition закрыт и профиль соответствует поддержанному режиму. Назначить `Part.in_work_object = body`; вызвать `ShapeFactory.add_new_pad(sketch, length)` с проверенным преобразованием единиц; при reverse настроить `Prism.direction_orientation` через enum.

Для up-to-plane/up-to-surface настроить `first_limit.limit_mode` и `first_limit.limiting_element`; размерный mode имеет другой набор обязательных аргументов. Не принимать одновременно несовместимые fields. После Update перечитать лимит и сравнить геометрию с ожидаемой. Новый disconnected volume может быть недопустим для выбранного Body, даже если sketch корректен.

### Контракт создания отверстия

Связанные карточки CATIA-050 и CATIA-064–067. Первая поддержанная реализация может принимать positioning sketch и depth: `add_new_hole_from_sketch(sketch, depth)`. После constructor настроить `diameter`, `type`, `bottom_limit`; для counterbore — head diameter/depth, для countersink — head angle/diameter. Для thread учитывать `hole_thread_description`, `thread_pitch`, `thread_depth` и `threading_mode`.

Задать дискриминируемый schema по типу отверстия. Нельзя требовать head_depth у простого отверстия или игнорировать его у counterbore. Центр, направление, основной диаметр и фактическое окончание отверстия проверяются отдельно. Plain face selection без координат/positioning constraint недостаточен для определения центра.

### Контракт solid Loft

Получить список минимум двух section References с orientation и closing point/reference для каждого. Вызвать `ShapeFactory.add_new_loft()`, привести generic wrapper к Loft и получить вложенный HybridShapeLoft. На нём вызвать `add_section_to_loft` в заданном порядке, затем `add_guide` для каждой направляющей и назначить coupling. Гладкость без support References не подразумевается.

Обновить solid Loft, а не только вспомогательный HybridShape. Проверить результат несколькими промежуточными сечениями. Не автоматически менять порядок или направление профилей при первой ошибке: вернуть сведения о неверной паре и явно поддержанный repair вариант.

### Контракт создания ограничений

Resolver возвращает References подходящих элементов и их role. `Constraints.add_mono_elt_cst`, `add_bi_elt_cst` и `add_tri_elt_cst` выбираются по type и числу элементов. Например, horizontal — одиночная линия, coincidence — допустимая пара геометрии, symmetry — три элемента с опорой. Названия enum и числа берутся из CATIA_AGENT_ENUMS.json.

Для размерного constraint назначить dimension через явные units, если параметр поддерживает `valuate_from_string`. Затем `Sketch.evaluate()` и проверка статусов. `evaluate()` возвращает None; это команда решателю, а не JSON с результатами Sketch Analysis. Публичный tool возвращает собственный диагностический отчёт после чтения constraints.

### Контракт измерения

Проверить `Measurable.geometry_name` перед чтением type-specific property. Radius не определён для произвольной грани, а расстояние между Body/HybridBody containers не эквивалентно расстоянию между допустимыми геометрическими References. В сборке использовать `get_measurable_in_context` и соответствующие in-context методы, если поддерживаются выпуском.

Ответ должен содержать измеренное значение, исходную единицу API, преобразованную публичную единицу и occurrence/frame. Null return annotation в Python не означает отсутствие возвращаемого значения: смотреть documented_return_type и COM signature. SAFEARRAY/getter адаптеры проверить на аналитических примерах перед включением capability.

Для новой геометрии проверять не только наличие имени в дереве, но и тип, принадлежность контейнеру, Update status и измеримые свойства. Для удаления материала сравнить объём до/после при допустимом измерительном контексте. Для поверхности проверить промежуточные сечения и границы. Для constraints проверить решённость, конфликты и сохранение замысла после изменения параметра.

Для drawing обновить generative view и проверить ссылки размеров. Для assembly проверить intended DOF и transforms; совпадение визуального положения не доказывает правильные constraints. Для экспорта открыть результат отдельным документом и сравнить габариты/объём с заданной погрешностью.

Offline tests проверяют JSON validation, units conversion, enum values, call order, обработку ошибок, идемпотентность и resolver ambiguity. Они не доказывают, что выбранное ребро CATIA обработано правильно. Windows integration tests должны создавать одноразовые документы с заранее заданными простыми геометриями и проверять фактические результаты.

## Документация и воспроизводимость

Список исходных страниц, их SHA256 и SHA256 официального wheel находятся в `CATIA_AGENT_SOURCE_MANIFEST.json`. Wheel использован для статического чтения исходников; CATIA и pycatia здесь не запускались. Для установленной версии CATIA повторно проверить лицензии, типовую библиотеку COM и доступные интерфейсы.

Ссылки `latest` изменяемы. Зафиксировать pycatia 0.10.1 при разработке adapter либо явно пересобрать каталог для другой версии. Поля `source_file` и `source_line` относятся к проверенному wheel. Для каждой выпущенной capability записывать тестовый выпуск CATIA, service pack и результаты live tests.

Готовность определяется выполнением контракта и геометрическими тестами. Число методов в каталоге не является числом проверенных возможностей агента.
