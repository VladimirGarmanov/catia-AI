# Проверка ограничений эскиза

`catia_sketch_constraint_status` проверяет доступные данные ограничений без
изменения CATIA. По умолчанию читает привязанный открытый Sketch. Для закрытого
эскиза передай свежий `sketch_handle` из `catia_list_objects`.

```json
{"sketch_handle": "obj_...", "require_fully_constrained": true}
```

Инструмент возвращает:

- `constraint_health`: `satisfied`, `problems_detected`, `no_constraints`,
  `no_active_constraints` или `unknown`.
- Активные, отключённые, reference и driving ограничения; точные handles
  проблемных constraints, native status, доступный размер и ошибки чтения.
- `up_to_date` / `status_freshness`: рассчитан ли эскиз по последним спецификациям.
- `fully_constrained`, `iso_constrained`, `remaining_dof`: `null`, если доказать
  полноту ограничений нельзя. `null` не означает false или нулевое число DOF.

При `require_fully_constrained=true` неизвестный результат **не проходит**:
возвращается `ok=false`, MCP `isError=true`, код `FULLY_CONSTRAINED_UNVERIFIED`.
Проблемные активные ограничения дают `CONSTRAINTS_NOT_SATISFIED`, неактуальная
модель — `UPDATE_REQUIRED`. Подробный отчёт сохраняется в ответе.
Без строгого режима `ok=true` означает успешное чтение, а не fully constrained.

**Ограничение:** проверенная [CAA Sketch Automation reference](https://catiadesign.org/_doc/V5Automation/generated/interfaces/SketcherInterfaces/interface_Sketch_21197.htm)
описывает коллекцию Constraints и метод Evaluate, но не предоставляет
документированный getter полноты ограничений/DOF всего эскиза.
[Constraint.Status](https://catiadesign.org/_doc/V5Automation/generated/interfaces/MecModInterfaces/interface_Constraint_21016.htm)
проверяет отдельное ограничение. Поэтому все статусы OK не доказывают отсутствие
свободных степеней или избыточности. Число constraints тоже не является рангом
системы. Reference-размер измеряет геометрию, а не задаёт её положение.

Инструмент не вызывает Evaluate, Update, OpenEdition или CloseEdition, не
трогает выбор и геометрию. При устаревшем результате нужно явно закончить
редактирование, обновить модель и перечитать. Для окончательного ответа по
fully/under/over-constrained нужен native Sketch Analysis в CATIA; пользователь
может открыть его вручную, после чего агент прочитает доступный скриншот.
Снимок обычных зелёных линий не заменяет такую проверку. UI-ввод запрещён.

Существующий `catia_sketch_diagnose` использует тот же reader и больше не
возвращает `all_constraints_satisfied=true` для пустого или полностью отключённого
набора. Ограничение чтения — 1000 записей по умолчанию, максимум 5000; усечённый
отчёт не выдаётся за полную проверку. В частичных COM-ошибках поля остаются unknown.

Windows probe: в новой несохранённой детали сравнить отчёт с native Sketch
Analysis для свободной линии, полностью ограниченного прямоугольника,
отключённого ограничения и конфликтующих размеров. До/после сравнить геометрию,
выбор и открытость Sketch. Offline doubles проверяют ветвления и read-only
поведение, но не доказывают работу native CATIA solver.
