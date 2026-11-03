# Переименование объектов CATIA

Раньше были отдельные rename modes для сборок и чертежей, но не общий способ
переименовать существующий Pad, Pocket, Sketch или Body. Теперь есть
`catia_rename_object`: один инструмент для Codex и Claude Code.

Последовательность:

1. Прочитать `catia_get_model_state` для document_id/revision.
2. Получить целый tree handle через `catia_list_objects` для CATPart или
   `catia_domain_objects` для CATProduct/CATDrawing. Для constraint/product
   handles также подходит `catia_assembly_inspect`.
3. Вызвать `catia_rename_object` с handle, new_name, document_id,
   expected_revision, уникальным request_id. Можно передать expected_name,
   чтобы обнаружить переименование пользователем между чтением и записью.
4. Проверить old_name/new_name/changed в результате; при необходимости перечитать
   дерево. Геометрический Update и screenshot ради имени не нужны.

Например: «Переименуй Pad.1 в BasePad, Sketch.1 в BaseProfile и PartBody в
BracketBody». Агент сначала получает реальные handles; не подставляет имена
вместо handles и не пересоздаёт геометрию. Каждая запись имеет собственный
request_id и текущую ревизию после предыдущей операции.

| Объект | Семантика |
| --- | --- |
| Part feature: Pad, Pocket, Shaft, Hole, fillet, pattern и другие в Shapes | Имя узла Name |
| Body, HybridBody, OrderedGeometricalSet, Sketch, GSD geometry | Name после проверки принадлежности текущему Part |
| Sketch primitive/constraint, relation, axis system | Name; встроенные sketch/origin axes исключены |
| Изменяемый настоящий параметр текущего Part | `Parameter.Rename(new_name)`, global name; значение не меняется |
| Прямой компонент сборки | Instance Name; исходный ReferenceProduct/PartNumber не меняется |
| Root assembly constraint/publication | Name |
| Drawing sheet/view/text/table/dimension/GDT/explicit primitive | Name; у view это prefix, у text не отображаемый Text |

Это не универсальный доступ ко всем COM Name: коллекции, приложение, документы,
файлы, топологические грани/рёбра и произвольные объекты не являются целями.
Root Product PartNumber изменяется через `catia_assembly_operation` mode=metadata.
Для отображаемого текста используй `catia_drawing_text_edit` mode=content.
Для файла нужен отдельный явно разрешённый SaveAs с путём.

Пустые/управляющие имена и окружающие пробелы отклоняются; дубликаты в той же
коллекции проверяются без учёта регистра. Остальную допустимость имени решает
CATIA: строки не обрезаются и не исправляются незаметно. Старый CAA справочник
описывает более строгие правила имён; поддержка пробелов/Unicode на конкретном
релизе требует живой проверки. Local: у параметров не принимается.

Metadata-only операция не запускает Update и не закрывает открытый Sketch.
Если имя уже совпало, возвращается changed=false. Даже при этом следует брать
новую revision из ответа, поскольку сервер консервативно завершает write request.
При COM-ошибке или несовпадении readback: ошибка MCP с modified_handles и
partial_failure, без автоматического rollback/повторной записи. Native Name
может быть read-only у отдельных объектов — это ошибка, а не успешное сообщение.
Формулы/внешние макросы, которые ищут объект по строковому имени, стоит проверить
после переименования; успешный readback этого не доказывает.

## Ручная Windows-проверка

На новой несохранённой детали создать Sketch/Pad и дать им новые имена, затем
прочитать дерево и проверить сохранность геометрии/связей. Повторить для открытого
Sketch без закрытия edition, GSD geometry и именованного параметра с формулой.
Проверить дубликат, переименование между чтением и записью, выбранную грань
(должна быть отклонена). На тестовой сборке проверить instance Name без изменения
reference PartNumber; на чертеже — view prefix и имя текста без изменения Text.
Отдельно проверить Unicode и пробелы на целевой CATIA. Offline mocks не
подтверждают COM, обновление надписей в UI или зависимости от старых имён.

Контракты CAA: [AnyObject.Name](https://catiadesign.org/_doc/V5Automation/generated/interfaces/System/interface_AnyObject_9080.htm),
[Parameter.Rename](https://catiadesign.org/_doc/V5Automation/generated/interfaces/KnowledgeInterfaces/interface_Parameter_25302.htm).
Это зеркало документации Dassault, не сайт Dassault.
