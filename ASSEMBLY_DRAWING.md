# Assembly и Drawing

Обновление от 2026-11-04 добавляет пространственный контекст, preview опор
и typed mate с **10 режимами** поверх предыдущих Assembly-инструментов.
Всего сервер регистрирует **176 full / 13 inspection**; существующие
имена сохранены. Это конкретное покрытие API, не вся GUI CATIA и не заявление
о проверке на Windows. Runtime остаётся direct pywin32 COM, общий для Codex и Claude.

## Сначала весь план, затем последовательность команд

Цель — завершить разрешённую сборочную задачу без постоянного «продолжать?».
Это не массовая отправка непроверенных COM-вызовов. Агент анализирует задачу
целиком, затем последовательно исполняет этапы, проверяя каждый ответ. Между
успешными командами не нужна новая авторизация на уже согласованный объём.

1. Прочитать workspace/model/selection и `catia_assembly_spatial_context`.
   Получить таблицу «экземпляр → родитель → поза относительно корня → роль».
   Названия — подписи; записи выполняются по handles. Для вложенных деталей
   поза вычисляется как `T_root_child = T_root_parent × T_parent_child`.
   Оси хранятся столбцами, перенос — мм. Отсутствующая поза предка делает
   положение потомков неизвестным. `spatial_complete=false` запрещает делать
   выводы о всей сборке по неполным данным.
2. Сопоставить детали с чертежом: база, вал, опоры, колесо, крепёж; отделить
   прочитанные факты от предполагаемого назначения. Начало детали не является
   её центром, осью отверстия или габаритом. Этот инструмент не измеряет BRep
   плоскости, зазоры и пересечения и не распознаёт роль детали автоматически.
3. Записать граф сопряжений: пара компонентов, точные опоры, тип связи,
   сторона/ориентация/размер, желаемая подвижность, порядок и проверка результата.
   Выбрать опорный компонент, но не создавать Fix. Относительные связи могут
   оставлять глобальное движение сборки; это явно сообщается пользователю.
4. До записи проверить фактические schemas и доступность опор. Существующие
   геометрические оси/плоскости и подготовленные при моделировании datum-элементы
   предпочтительнее догадок по граням. Publications помогают обозначить интерфейсы,
   но их имя само по себе не становится устойчивым Reference. Новые mate tools
   принимают текущее точное выделение; не строят BRep-пути по строкам.
5. Выполнить весь согласованный этап: позиционирование → совмещение осей →
   посадочные плоскости/смещения → угловая ориентация → итоговая проверка.
   План может содержать десятки вызовов. Для будущих шагов хранить смысл опор,
   а handles/revision подставлять только после свежего чтения перед записью.
   После каждого write handles выделения устаревают; нельзя переиспользовать
   пачку заранее подготовленных JSON-вызовов с одной revision.
6. Между удачными шагами продолжать автоматически. Использовать встроенный
   Update/readback инструмента, не повторять их без причины. После логической
   группы связей прочитать spatial context и `catia_assembly_constraint_status`.
   В конце проверить положение, связи и требуемые зазоры отдельно. Скриншот —
   для существенной визуальной проверки/ошибки, не после каждой команды.
   При failed/partial_failure/timeout остановить зависимые шаги и сверить модель.

### Три новых инструмента

| Инструмент | Назначение |
| --- | --- |
| `catia_assembly_spatial_context` | Дерево, положения в общей системе, constraints/publications, полнота чтения; без Update |
| `catia_assembly_mate_preview` | Два свежих selection handles → владельцы, измеренный тип геометрии, позы, совместимые режимы; без записи/проверки разрешимости |
| `catia_assembly_mate` | Одна связь с начальным именем и настройками до Update; native status, readback настроек и поз до/после |

`mate` требует name, mode, два selection_handles и обычные document_id,
expected_revision, request_id. Геометрия проверяется через SPA GeometryName,
а не по имени объекта. Оба владельца должны быть разными непосредственными
детьми корня. Вложенное редактирование и неявное изменение исходных деталей
не поддерживаются. Дубликат имени связи отклоняется; семантическую избыточность
связей проверяет агент/solver, а не поиск похожих имён.

| Режим | Опоры и native type | Дополнительные входы |
| --- | --- | --- |
| `axis_coincidence` | две точные линии, On=2 | orientation |
| `axis_parallel` | две линии, Parallelism=8 | orientation |
| `axis_perpendicular` | две линии, Perpendicularity=11 | — |
| `plane_coincidence` | две плоскости, On=2 | orientation |
| `plane_offset` | две плоскости, Distance=1 | distance_mm ≥ 0, side, orientation |
| `plane_parallel` | две плоскости, Parallelism=8 | orientation |
| `plane_perpendicular` | две плоскости, Perpendicularity=11 | — |
| `plane_angle` | две плоскости, Angle=6, sector=0 | angle_deg 0…180 |
| `plane_contact` | две плоскости, SurfContact=20 | — |
| `point_coincidence` | две точки, On=2 | — |

orientation: same/opposite/undefined, side: positive/negative/undefined.
`undefined` оставляет соответствующий выбор solver, не гарантирует нужную сторону.
`axis_*` здесь связывает **две линии**, а не native mono-element AxisParallelism
относительно глобального X/Y/Z. Цилиндрическая грань, окружность и целый AxisSystem
не подменяются осью. Preview возвращает для такой пары пустой список typed modes;
это известная граница, не повод выбирать «Concentricity» наугад.

Пример замысла для вала и свободно вращающегося колеса: соосность двух datum-линий,
затем расстояние между торцевыми плоскостями. Для изолированной идеальной пары
соосность оставляет вращение и осевое перемещение; посадочная плоскость может
убрать осевое перемещение. Вращение сохраняется по замыслу. У неподвижного шкива
может потребоваться отдельная угловая связь. Это качественная оценка проекта,
**не вычисленный DOF**. Не добавлять parallel поверх совпадающих осей/плоскостей
ради количества команд и не убирать намеренную подвижность лишними связями.

### Пример цепочки для подготовленных опор

```text
get_model_state → spatial_context → план всей сборки
get_selection → mate_preview(две оси-линии)
mate(axis_coincidence, orientation=по плану, name=Wheel_Axis)
get_selection заново → mate_preview(две посадочные плоскости)
mate(plane_offset, distance_mm=по чертежу, side/ orientation=по плану, name=Wheel_Seat)
spatial_context → assembly_constraint_status
[следующая пара деталей по тому же плану]
финальная проверка положения, связей и подвижности
```

Это последовательность намерений, не готовый JSON с выдуманными handles.
Если нужные плоскости ещё не выделены, получить точное выделение разрешённым
способом или попросить пользователя выбрать их. Не создавать заменяющую
геометрию в чужом документе и не повторять неопределённую запись через UI.

### Что покрывает текущий Assembly-набор

| Задача | Инструменты / границы |
| --- | --- |
| Найти детали, вложенность, позы, references | domain_objects, assembly_inspect, assembly_component_details, spatial_context |
| Разместить/повернуть, вставить/заменить/повторить | assembly_component, insert_document, replace_component, duplicate_component, pattern, transform |
| Оси, плоскости, посадки, угол | mate_preview + mate; точные опоры обязательны |
| Касательность, симметрия, трёхэлементные связи | assembly_constraint; совместимость конкретных опор решает CATIA |
| Править/подавлять/удалять одну связь | assembly_constraint; удаление только явно, Fix создавать/активировать нельзя |
| Статус solver и размер связи | assembly_inspect, assembly_constraint_status; global DOF неизвестен |
| Publications, BOM, metadata | assembly_publication, publication_relay, assembly_bom, set_metadata |
| Clash/clearance, кинематика | отдельные scoped DMU tools и лицензия; позы и Status=0 этого не доказывают |

### Источники и Windows-приёмка

Проверены CAA-страницы [CatConstraintType](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/enum_CatConstraintType_27587.htm),
[Constraints](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/interface_Constraints_22166.htm),
[Constraint](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/interface_Constraint_21016.htm),
[Orientation](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/enum_CatConstraintOrientation_42617.htm),
[Side](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/enum_CatConstraintSide_27170.htm),
[Measurable](https://catiadesign.org/_doc/V5Automation/generated/interfaces/SpaceAnalysisInterfaces/interface_Measurable_34815.htm)
и [CatMeasurableName](https://catiadesign.org/_doc/V5Automation/generated/interfaces/SpaceAnalysisInterfaces/enum_CatMeasurableName_40819.htm).
Это зеркало документации Dassault, не домен Dassault. CAA прямо различает On,
Concentricity и orientation/side; generic 3D Concentricity описывает сферы.
GUI-выбор оси цилиндра нельзя без проверки приравнять к Reference всей поверхности.

Изменение поведения AI задаётся общим AGENTS.md и launcher/handoff-инструкциями
для Codex/Claude; новая модель/API-подписка не добавляется. Поддержка AGENTS.md
описана в [OpenAI documentation](https://developers.openai.com/codex/guides/agents-md).

На Windows проверить в новой тестовой CATProduct: две разные детали с явными
datum-линиями/плоскостями; preview типов; каждый нужный режим mate; настройки
до Update; status/readback; поворот и перенос вложенной подсборки с ручной
сверкой root-поз; отказ на устаревшем выделении/цилиндре вместо линии; solver
ошибку без повторного создания. Отдельно проверить перемещение связанных
соседей и сохранение намеренного вращения. До этого native выполнение остаётся
непроверенным: offline-моки проверяют контракты, математику преобразований и ошибки.

## Новые инструменты сборки

Исправлен также старый `catia_move_component`: Position читается через явный
by-reference SAFEARRAY, а не через нулевой Python-список. Вызов с нулевыми
приращениями только читает позу, не вызывает SetComponents/Update и не повышает
revision. Ошибка чтения до записи имеет статус `failed`, а не `partial_failure`.
`POSITION_UNAVAILABLE` означает, что массив не прочитан; `INVALID_COMPONENT_POSE`
содержит реально полученную некорректную матрицу. `catia_list_components` при
ошибке возвращает position=null и описание причины, а не фиктивное положение (0,0,0).
На Windows ещё нужно проверить этот путь с реальным late-bound pywin32.

| Инструмент | Что делает |
| --- | --- |
| `catia_assembly_component_details` | Читает свойства экземпляра/reference, доступный исходный документ и handles его публикаций |
| `catia_assembly_bom` | Возвращает структурированную спецификацию: терминальные детали (`leaf`), непосредственные дети (`top`) или все уровни (`all`) |
| `catia_assembly_constraint_status` | Показывает проблемные связи, native broken/unupdated counts, состояние активных constraints; `require_satisfied=true` требует положительной проверки |
| `catia_assembly_get_positions` | Читает исходные позиции выбранных экземпляров для последующего явного восстановления |
| `catia_assembly_insert_document` | Вставляет ссылку на уже открытый CATPart/CATProduct по `source_document_id`, без активации или сохранения исходника |
| `catia_assembly_duplicate_component` | Создаёт ещё один экземпляр той же reference-детали с новым именем и заданной позой |
| `catia_assembly_replace_component` | Заменяет один экземпляр ссылкой на открытый документ; сохраняет имя, опционально позу; проверяет соседние ссылки и состояние связей |
| `catia_assembly_pattern` | Линейный/круговой массив экземпляров с общим reference, с заданными именами и положениями |
| `catia_assembly_transform` | Групповые `set_positions`, `translate`, `rotate` вокруг явно заданной оси и точки |
| `catia_assembly_explode` | Разносит экземпляры по явно заданным векторам; возвращает исходные позы и параметры обратного `set_positions` |
| `catia_assembly_set_metadata` | Меняет выбранные свойства корня: PartNumber, Revision, Definition, Nomenclature, DescriptionRef, Source |
| `catia_assembly_publication_relay` | Создаёт публикацию корня, ссылающуюся на существующую публикацию непосредственного компонента |

### Экземпляры, исходники и файлы

Перед записью читать `catia_get_model_state`, `catia_get_workspace_state` и
`catia_assembly_inspect`/`catia_domain_objects`. Источник для вставки/замены задаётся
точным ID открытого документа. Целью остаётся активный связанный CATProduct.
При вставке проверяется, что исходник не содержит эту сборку: цикл запрещён.
Исходные файлы не редактируются и не сохраняются; автоматической смены окна нет.
Ссылки на несохранённые детали живут в текущей CATIA-сессии. Для переносимой
сборки нужно отдельно сохранить исходные детали и сборку по разрешённым путям.

Duplicate и Pattern создают **экземпляры одной reference**, а не независимые
копии CATPart. Их геометрия общая. Сопряжения исходного экземпляра не копируются.
Массив не является нативной ассоциативной feature: изменение шага требует явной
правки поз. `count` включает исходный экземпляр и ограничен 2–50.

Линейный `step_mm` — вектор между соседними экземплярами в системе родителя.
Круговой режим принимает `axis`, `pivot_mm`, `angle_step_deg` и
`rotate_orientation`. Для N экземпляров по окружности шаг равен `360/N`:
исходник занимает первое место, копия при 360° не создаётся. Например, seed
в `(30,0,0)`, ось `(0,0,1)`, pivot `(0,0,0)`, count=6, step=60°.
При `rotate_orientation=false` изменяются положения начал, ориентации сохраняются.
Пересечения и механическая пригодность массивом автоматически не проверяются.

### Групповые перемещения и разнесение

Перед разнесением сначала прочитать и сохранить ответ `catia_assembly_get_positions`.
При успешном `explode` исходные позы также есть в `before_positions`/`restore`.
При частичной ошибке ответ успешного разнесения может отсутствовать — заранее
прочитанные позы нужны для анализа восстановления. Автоматического Undo нет.

`explode` меняет реальные позиции компонентов, не создаёт CATIA Scene. Смещения
задаются для каждого handle явно, без угадывания зазоров по bounding box.
Восстановление: перечитать состояние, вызвать `catia_assembly_transform` с
`mode=set_positions`, исходными позами, свежими revision/request_id.
Все элементы пакета проверяются до первой записи; после Update перечитываются
все целевые позы. Ограничения не отключаются. Если solver сдвинул компонент
обратно, возвращается ошибка; уже выполненные перемещения не откатываются.

### Сцены (DMU Product-Scenes) для разнесённого вида

Для презентационного разнесения без изменения реальных поз используйте сцены.
`catia_assembly_scene_inspect` (read-only) перечисляет сцены активного CATProduct
(index, handle, name, full/partial) и, при `scene_handle`+`component_handles`,
реальные и сценовые позы; без перегрузки в сцене поза равна `null`, данные не
создаются. `catia_assembly_scene`: `create` (ProductScenes.AddProductSceneFull/
AddProductScenePartial с корневым Product), `set_component_positions` (12 значений,
оси-столбцы, мм), `explode_linear` (k-й экземпляр списка сдвигается на
k·`spacing_mm` вдоль `direction` от реальной позы), `explode_offsets`, `remove`
(требует `expected_name`). Запись через SceneProductData.Position.SetComponents,
затем readback и проверка неизменности реальных поз (иначе POSTCONDITION_FAILED).
Product Update не вызывается. Применения сцены к изделию в CAA нет — не
предлагается. Ошибка COM/лицензии DMU → CAPABILITY_UNAVAILABLE без отката к
`catia_assembly_explode`. Система координат сценовой позы предполагается как
у Product.Position; требуется проверка в Windows CATIA.

Групповой `rotate` поворачивает и базис, и положение начала компонента вокруг
`pivot_mm`. Это отличается от старого `catia_assembly_component(mode=rotate)`,
который вращает компонент вокруг его собственного начала.

### BOM, связи и свойства

BOM объединяет позиции по COM-идентичности `ReferenceProduct`, не по PartNumber:
две разные детали с одинаковым обозначением остаются разными строками. Для `all`
учитываются и подсборки, и вложенные экземпляры; для `leaf` только терминальные
экземпляры. Числа при `truncated=true` неполные. Путь имён — подпись, не ID.

`catia_assembly_constraint_status` не запускает solver. Пустой набор, только
неактивные связи, неполное чтение или неподтверждённая актуальность дают неизвестный
результат; известная проблема даёт `all_active_satisfied=false`.
Даже `all_active_satisfied=true` не доказывает полноту ограничений:
`fully_constrained` и `remaining_dof` остаются `null`.

Metadata пишет только в корень активного CATProduct. `source` принимает
`unknown`, `made`, `bought`. Reference-свойства внешнего компонента через этот
инструмент не меняются. `publication_relay` требует два точных handles: компонент
и принадлежащую ему публикацию. Сигнатура CAA `SetRelay` принимает коллекцию
`Publications`; текст старой справки называет её Product. Реальная совместимость
и идентичность `Valuation` требуют Windows-пробы; несовпадение не считается успехом.

### Новые режимы catia_assembly_constraint

| Режим | Контракт |
| --- | --- |
| `tangent` | Две совместимые 3D-опоры; native тип 4 |
| `sphere_concentric` | Две сферы с общим центром; native тип 3, **не соосность цилиндров** |
| `symmetry` | Две опоры и третья опора симметрии — линия/плоскость; native тип 15 |
| `planar_angle` | Две плоскости и линия их пересечения; угол в градусах, native тип 7 |
| `distance_three` | Две опоры и третья, задающая направление измерения; mm, native тип 1 |
| `angle_sector` | Сектор 0–3 существующей угловой связи; CATIA также меняет angle/side/orientation |
| `distance_direction` | `free`, `x`, `y`, `z` для существующего расстояния |
| `driving_mode` | Driving или driven/reference dimension для расстояния/угла |

Новые связи используют `AddBiEltCst`/`AddTriEltCst` и свежие точные selection
references. Поддержку конкретной комбинации геометрии решает CATIA; индексы
граней или отображаемые имена не превращаются в устойчивые ссылки. Fix запрещён
во всех новых режимах, включая редактирование уже существующего Fix.

## Сборки

| Инструмент | Режимы / данные |
| --- | --- |
| `catia_assembly_inspect` | Дерево occurrences, metadata, root constraints, publications, optional parent-relative poses; ограничение глубины/числа объектов |
| `catia_assembly_component` | new_component, import_file, rename, description, remove, set_position, translate, rotate, update |
| `catia_assembly_constraint` | coincidence, parallel, perpendicular, contact, distance, angle, edit_value, orientation, side, activate, deactivate, remove, rename, replace_element; дополнительные режимы выше |
| `catia_assembly_publication` | rename, rebind, remove |

Прежний `catia_assembly_operation` сохраняет создание подпродуктов, повторные
occurrences, замену компонента из файла, metadata корня, work mode, публикацию
выделения и файловый BOM с прежними ограничениями. Fix и Fix Together отключены.

Новые occurrence-записи работают только с непосредственными детьми активного
CATProduct. Иначе изменение структуры внешней подсборки может изменить другой
документ. Вложенное дерево читается, но для записи нужно явно выбрать целевой
документ. Reference metadata внешних деталей не изменяется.

Положение — 12 чисел: три оси столбцами (X, Y, Z), затем XYZ в миллиметрах в
системе родителя. Проверяется ортонормальность и правая ориентация. Rotate
вращает вокруг собственного начала компонента относительно оси в системе
родителя, не вокруг начала сборки. После Update читается решённая поза.
Если solver вернул компонент назад, результат `POSTCONDITION_FAILED`.

### Проверка чтения положения на Windows

После UPDATE и перезапуска AI-сессии оставить нужный CATProduct активным:

1. `catia_get_model_state`, затем `catia_assembly_inspect` с `include_positions=true`.
   У нужного экземпляра должны вернуться 12 конечных чисел `axis_components`;
   `unavailable.axis_components`/отсутствие позы не считаются успехом чтения.
2. По свежему occurrence handle вызвать `catia_assembly_get_positions`.
   Сравнить позу с inspection. Оба вызова только читают, без Update/SetComponents.
3. Для регрессии legacy Move вызвать `catia_move_component` с точным уникальным
   именем экземпляра, всеми шестью приращениями = 0, свежими document_id/revision
   и новым request_id. Ожидаются та же поза, `changed=false`, `updated=false`
   и неизменённая revision. Не повторять прежний request_id с закешированной ошибкой.
4. Реальное смещение и его readback проверять отдельно только на явно выбранной
   тестовой сборке. Успешное чтение не доказывает работу solver/перемещения.

Адаптер SAFEARRAY использует untyped `IDispatch.Invoke`, чтобы generated wrapper
pywin32 не отвергал VARIANT с ошибкой `Objects for SAFEARRAYS must be sequences`.
Если ошибка остаётся, нужен полный `message`: он теперь содержит имя метода,
путь вызова и тип исключения. Не заменять недоступную позу нулевой/единичной.

Связи требуют текущие selection handles с настоящими COM Reference и
проверяемым LeafProduct. Имена/номера рёбер не используются как ID. Значения
distance — mm, angle — deg, передаются через `ValuateFromString`; после Update
читаются dimension и Status. Удаление явно вызывается пользователем, не rollback.

## Чертежи

| Инструмент | Режимы / данные |
| --- | --- |
| `catia_drawing_inspect` | overview, view, text, table (диапазон ячеек), dimension (измеренные параметры) |
| `catia_drawing_sheet_setup` | format (ISO/ANSI/Letter/Legal), custom_format, projection (1st/3rd angle), rename, scale, activate, update, force_update, remove |
| `catia_drawing_view_modify` | position, angle, rename, lock, frame, alignment, activate, update, force_update, unclip, unbreak, unbreakout, remove |
| `catia_drawing_text_edit` | content, position, angle, font, frame, leader, remove |
| `catia_drawing_table` | create, cells, insert_row/column, remove_row/column, row_size/column_size, merge, unmerge, alignment, cell_font, position, angle, remove |
| `catia_drawing_geometry` | point, line, circle, arc, rectangle, polyline; construction flag |
| `catia_drawing_dimension_edit` | restore_position, unclip, clip, value_auto, remove |

Прежние инструменты создания ассоциативных видов, разрезов, размеров,
допусков, текста/GDT и title block остаются.

`catia_drawing_annotation(mode=balloon)`: `text` (номер позиции), `position_mm`,
`head_mm` (конец выноски), `frame` = circle/scored_circle/oblong/ellipse
(CatTextFrameType 3/4/10/11). Создаёт DrawingText, `ActivateFrame` и одну
выноску, затем Update листа и readback FrameType/Text. Это НЕ нативный балун
Generate Balloons: связи с компонентом и строкой BOM нет, нумерацию и
соответствие таблице `catia_assembly_bom`/`catia_drawing_table` обеспечивает
агент. При несовпадении readback — POSTCONDITION_FAILED, текст остаётся в
`created_handles`. Привязку выноски к геометрии проверить визуально в Windows CATIA. `catia_domain_objects` теперь
также выдаёт table/GDT handles, root assembly constraints/publications.

Новые 2D primitives — неассоциативная геометрия во view-local mm, без
автоматического наследования constraints. После записи Factory2D вызывается
SaveEdition (это не сохранение файла). Глобальный источник 3D не изменяется.
Размер чертежа измеряет геометрию: новые presentation modes не подменяют его
значение произвольным текстом.

Table indices начинаются с 1; для вставки before_index=0 добавляет в конец.
Сначала проверяются все ячейки пакета, затем запись. Пакет не атомарен при
COM-ошибке. Merge/unmerge вызывают native API; геометрия объединения отдельно
не прочитывается. Table/Sheet/View размеры и позиции — mm, углы ввода — deg.
Новый текстовый editor переводит position_mm в метры для DrawingText.x/y,
как указано в CAA. Это отдельный контракт от DrawingTexts.Add и требует
проверки единиц на целевой версии CATIA. Не применяется к 2D Layout for 3D Design.

## Выполнение и ошибки

1. `catia_get_model_state`, затем domain/assembly/drawing inspection.
2. Передать document_id, expected_revision и уникальный request_id в запись.
3. Выполнить одну операцию. Update владельца входит в новые mutation tools;
   Part-only `catia_update_part` для Product/Drawing не вызывать.
4. Прочитать изменённые свойства; screenshot только для визуально значимой проверки.

Объект проверяется на принадлежность конкретной коллекции до изменения.
Ошибка Update или несовпадение readback — ошибка MCP. Если часть объектов уже
создана, сервер сохраняет created_handles и partial_failure, без удаления/отката.
Отсутствующий SAFEARRAY/COM property не заменяется нулевыми координатами.
После внешнего UI-изменения перечитать контекст: revision отслеживает сервер,
а не произвольные пользовательские изменения.

## Проверки на Windows, которые ещё нужны

- Создание/импорт occurrences без смены активного документа; rename/remove
  не меняют исходные CATPart/CATProduct на диске.
- Position.GetComponents SAFEARRAY, перемещение/вращение свободного и связанного
  компонента, отказ при solver mismatch.
- Exact Reference + LeafProduct для contact, distance, angle и replacement;
  solver statuses, suppression, orientation/side, публикации и их consumers.
- ISO/ANSI/custom paper, orientation/first-third projection, view origin/angle,
  align/lock, генеративный update и удаление clipping/breakout.
- DrawingText x/y units, font/frame/leader; Table cells, insert/remove, merge,
  шрифты и визуальная компоновка; 2D primitives и SaveEdition при отказе.
- Размеры сохраняют реальную associativity после presentation-правок.
- INSTALL обоих клиентов с нуля без Git/admin, Claude sign-in, `/mcp`, image/PDF
  чтение и реальный write/readback. Offline registration не заменяет эти проверки.

### Windows-проба нового Assembly workflow

На новых тестовых документах, сохранив пользовательские документы отдельно:

1. Создать два разных CATPart и пустой CATProduct. Вставить оба открытых источника
   по ID; проверить, что active document не поменялся и источники не изменились.
2. Дублировать один компонент; убедиться, что появился экземпляр той же reference.
   Проверить линейный массив из 4 элементов и круговой из 6 с шагом 60°.
3. Прочитать позиции. Выполнить групповой перенос, вращение вокруг внешней точки,
   explode и явный restore. Проверить `Position.GetComponents` на целевой версии.
4. Повторить перемещение на связанном компоненте: несовпадение с запрошенной позой
   должно быть ошибкой. Не повторять неопределённый COM-вызов.
5. Заменить один из одинаковых экземпляров другим открытым CATPart; соседние
   экземпляры должны сохранить прежнюю reference. Проверить broken mates.
6. Проверить BOM с повторяющейся подсборкой и двумя разными деталями с одинаковым
   PartNumber: количества и группировка должны соответствовать реальному дереву.
7. Проверить новые типы связей на заведомо совместимых опорах, направление/сектор,
   native statuses и отказ изменения Fix. Проверить relay публикации и её consumer.
8. При явном разрешении сохранить исходники и сборку, открыть заново и проверить
   ссылки. Не считать успешную вставку несохранённого документа проверкой дисковых ссылок.

Offline-тесты покрывают маршрутизацию, матрицы, владение объектами, частичные
ошибки, дедупликацию запросов и MCP isError. Они не проверяют native solver,
COM SAFEARRAY или геометрию. Все перечисленные Windows-пробы ещё предстоят.

Контракты взяты из кеша CAA V5 Automation (копия документации Dassault, не домен
Dassault): [Product/Products](https://catiadesign.org/_doc/V5Automation/generated/interfaces/ProductStructureInterfaces/interface_Products_41084.htm),
[Constraint](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/interface_Constraint_21016.htm),
[Constraint types](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/enum_CatConstraintType_27587.htm),
[Position](https://catiadesign.org/_doc/V5Automation/generated/interfaces/InfInterfaces/interface_Position_14902.htm),
[Publications](https://catiadesign.org/_doc/V5Automation/generated/interfaces/ProductStructureInterfaces/interface_Publications_45134.htm),
[DrawingSheet](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingSheet_26492.htm),
[DrawingView](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingView_25425.htm),
[DrawingText](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingText_25520.htm),
[DrawingTable](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingTable_26321.htm).
