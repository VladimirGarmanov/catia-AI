# Assembly и Drawing: расширение 2026-10-30

Добавлены **11 MCP-имён**, всего **146**, исходные 81 и все прежние 135 сохранены.
Новые имена группируют режимы операций. Это конкретное покрытие API, не вся GUI
CATIA и не заявление о проверке на Windows. Runtime остаётся direct pywin32 COM.

## Сборки

| Инструмент | Режимы / данные |
| --- | --- |
| `catia_assembly_inspect` | Дерево occurrences, metadata, root constraints, publications, optional parent-relative poses; ограничение глубины/числа объектов |
| `catia_assembly_component` | new_component, import_file, rename, description, remove, set_position, translate, rotate, update |
| `catia_assembly_constraint` | fix, coincidence, parallel, perpendicular, contact, distance, angle, edit_value, orientation, side, activate, deactivate, remove, rename, replace_element |
| `catia_assembly_publication` | rename, rebind, remove |

Прежний `catia_assembly_operation` сохраняет создание подпродуктов, повторные
occurrences, замену компонента из файла, metadata корня, work mode, публикацию
выделения, BOM и fix-together с прежними ограничениями.

Новые occurrence-записи работают только с непосредственными детьми активного
CATProduct. Иначе изменение структуры внешней подсборки может изменить другой
документ. Вложенное дерево читается, но для записи нужно явно выбрать целевой
документ. Reference metadata внешних деталей не изменяется.

Положение — 12 чисел: три оси столбцами (X, Y, Z), затем XYZ в миллиметрах в
системе родителя. Проверяется ортонормальность и правая ориентация. Rotate
вращает вокруг собственного начала компонента относительно оси в системе
родителя, не вокруг начала сборки. После Update читается решённая поза.
Если solver вернул компонент назад, результат `POSTCONDITION_FAILED`.

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
допусков, текста/GDT и title block остаются. `catia_domain_objects` теперь
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
- Exact Reference + LeafProduct для Fix, contact, distance, angle и replacement;
  solver statuses, suppression, orientation/side, публикации и их consumers.
- ISO/ANSI/custom paper, orientation/first-third projection, view origin/angle,
  align/lock, генеративный update и удаление clipping/breakout.
- DrawingText x/y units, font/frame/leader; Table cells, insert/remove, merge,
  шрифты и визуальная компоновка; 2D primitives и SaveEdition при отказе.
- Размеры сохраняют реальную associativity после presentation-правок.
- INSTALL обоих клиентов с нуля без Git/admin, Claude sign-in, `/mcp`, image/PDF
  чтение и реальный write/readback. Offline registration не заменяет эти проверки.

Контракты взяты из кеша CAA V5 Automation (копия документации Dassault, не домен
Dassault): [Product/Products](https://catiadesign.org/_doc/V5Automation/generated/interfaces/ProductStructureInterfaces/interface_Products_41084.htm),
[Constraint](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/interface_Constraint_21016.htm),
[DrawingSheet](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingSheet_26492.htm),
[DrawingView](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingView_25425.htm),
[DrawingText](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingText_25520.htm),
[DrawingTable](https://catiadesign.org/_doc/V5Automation/generated/interfaces/DraftingInterfaces/interface_DrawingTable_26321.htm).
