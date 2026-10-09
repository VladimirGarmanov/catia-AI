# Каталог API инструментов CATIA V5 для Codex

Все 218 номеров соответствуют предыдущему справочнику. Это карта реализации; runtime и геометрические тесты ещё не выполнены. Статусы определены в [спецификации](CATIA_AGENT_IMPLEMENTATION_SPEC.md). Полный словарь свойств и методов возвращаемых классов: `CATIA_AGENT_API_SYMBOLS.json`. Числовые enums: `CATIA_AGENT_ENUMS.json`.

[Основной индекс pycatia](https://pycatia.readthedocs.io/en/latest/api_index.html) · [Исходники версии 0.10.1](https://pypi.org/project/pycatia/0.10.1/)

## Структура модели и управление построением

### 1 Part и CATPart

**CATIA-001 · workflow · P0**

Создать документ Part; проверить тип, вернуть идентификатор документа и Part. Не вызывать повторно при сетевом повторе запроса.

Проверка: Одна деталь не равна всей сборке.

API [Documents.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/documents.html#pycatia.in_interfaces.documents.Documents.add)

```python
add(document_type: str) -> AnyDocument
```

CATIA COM: `o Func Add(CATBSTR docType) As Document`.

API [PartDocument.part](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part_document.html#pycatia.mec_mod_interfaces.part_document.PartDocument.part)

```python
property part: Part
```

CATIA COM: `o Property Part() As Part`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 2 Body и PartBody

**CATIA-002 · direct · P0**

Создать Body в нужном Part. PartBody получать как main_body, не искать по локализованному имени.

Проверка: Проверь активное тело перед Pad или Pocket.

API [Bodies.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/bodies.html#pycatia.mec_mod_interfaces.bodies.Bodies.add)

```python
add() -> Body
```

CATIA COM: `o Func Add() As Body`.

API [Part.bodies](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.bodies)

```python
property bodies: Bodies
```

CATIA COM: `o Property Bodies() As Bodies`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Part.main_body](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.main_body)

```python
property main_body: Body
```

CATIA COM: `o Property MainBody() As Body`.

Свойство имеет setter.


### 3 Geometrical Set

**CATIA-003 · direct · P0**

Создать контейнер, задать имя, вернуть его handle.

Проверка: Группа сама не создаёт твёрдый объём.

API [HybridBodies.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/hybrid_bodies.html#pycatia.mec_mod_interfaces.hybrid_bodies.HybridBodies.add)

```python
add() -> HybridBody
```

CATIA COM: `o Func Add() As HybridBody`.

API [Part.hybrid_bodies](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.hybrid_bodies)

```python
property hybrid_bodies: HybridBodies
```

CATIA COM: `o Property HybridBodies() As HybridBodies`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 4 Ordered Geometrical Set

**CATIA-004 · direct · P0**

Создать ordered set; соблюдать порядок зависимостей, не подменять обычным HybridBody.

Проверка: Перестановка элементов может менять результат.

API [OrderedGeometricalSets.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/ordered_geometrical_sets.html#pycatia.mec_mod_interfaces.ordered_geometrical_sets.OrderedGeometricalSets.add)

```python
add() -> OrderedGeometricalSet
```

CATIA COM: `o Func Add() As OrderedGeometricalSet`.

API [Part.ordered_geometrical_sets](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.ordered_geometrical_sets)

```python
property ordered_geometrical_sets: OrderedGeometricalSets
```

CATIA COM: `o Property OrderedGeometricalSets() As OrderedGeometricalSets`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 5 Define In Work Object

**CATIA-005 · property · P0**

Установить конкретный объект в нужном Part. Зафиксировать прежний объект для восстановления контекста при ошибке.

Проверка: Не вставь новую операцию раньше нужной опоры.

API [Part.in_work_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.in_work_object)

```python
property in_work_object: AnyObject
```

CATIA COM: `o Property InWorkObject() As AnyObject`.

Свойство имеет setter.


### 6 Update

**CATIA-006 · direct · P0**

Полное или локальное обновление; затем проверить актуальность и измеримые постусловия.

Проверка: Исправляй первую ошибку в дереве.

API [Part.update](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.update)

```python
update() -> None
```

CATIA COM: `o Sub Update()`.

API [Part.update_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.update_object)

```python
update_object(i_object: AnyObject) -> None
```

CATIA COM: `o Sub UpdateObject(AnyObject iObject)`.

API [Part.is_up_to_date](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_up_to_date)

```python
is_up_to_date(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsUpToDate(AnyObject iObject) As boolean`.


### 7 Activate и Deactivate

**CATIA-007 · direct · P0**

Переключить активность feature и обновить зависимые элементы.

Проверка: Проверь зависимые операции после переключения.

API [Part.activate](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.activate)

```python
activate(i_object: AnyObject) -> None
```

CATIA COM: `o Sub Activate(AnyObject iObject)`.

API [Part.inactivate](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.inactivate)

```python
inactivate(i_object: AnyObject) -> None
```

CATIA COM: `o Sub Inactivate(AnyObject iObject)`.

API [Part.is_inactive](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_inactive)

```python
is_inactive(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsInactive(AnyObject iObject) As boolean`.


### 8 Hide и Show

**CATIA-008 · workflow · P0**

Очистить selection, добавить строго разрешённые объекты, изменить показ; отдельно восстановить пользовательский selection где возможно.

Проверка: Скрытие не означает отключение операции.

API [Selection.clear](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/selection.html#pycatia.in_interfaces.selection.Selection.clear)

```python
clear() -> None
```

CATIA COM: `o Sub Clear()`.

API [Selection.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/selection.html#pycatia.in_interfaces.selection.Selection.add)

```python
add(i_object: AnyObject) -> None
```

CATIA COM: `o Sub Add(AnyObject iObject)`.

API [Selection.vis_properties](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/selection.html#pycatia.in_interfaces.selection.Selection.vis_properties)

```python
property vis_properties: VisPropertySet
```

CATIA COM: `o Property VisProperties() As VisPropertySet`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [VisPropertySet.set_show](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/vis_property_set.html#pycatia.in_interfaces.vis_property_set.VisPropertySet.set_show)

```python
set_show(i_show: CatVisPropertyShow) -> None
```

CATIA COM: `o Sub SetShow(CatVisPropertyShow iShow)`.


### 9 Parents и Children

**CATIA-009 · partial · P0**

parent показывает контейнер Automation, а не полный граф геометрических зависимостей Parents and Children. Полный dependency graph здесь не подтверждён.

Проверка: Проверь зависимости перед удалением опоры.

API [AnyObject.parent](https://pycatia.readthedocs.io/en/latest/api/pycatia/system_interfaces/any_object.html#pycatia.system_interfaces.any_object.AnyObject.parent)

```python
property parent: 'AnyObject'
```

CATIA COM: `o Property Parent() As CATBaseDispatch`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [AnyObject.name](https://pycatia.readthedocs.io/en/latest/api/pycatia/system_interfaces/any_object.html#pycatia.system_interfaces.any_object.AnyObject.name)

```python
property name: str
```

CATIA COM: `o Property Name() As CATBSTR`.

Свойство имеет setter.


### 10 Change Sketch Support

**CATIA-010 · unconfirmed · P4**

Прямой setter Sketch.support отсутствует в pycatia 0.10.1. Изменение абсолютных осей не доказывает смену опоры. Пересоздание sketch требует переноса constraints и зависимых features; отдельная операция с явным риском потери ссылок.

Проверка: Контролируй оси, зеркальность и внешние ссылки.

API [Sketch.set_absolute_axis_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.set_absolute_axis_data)

```python
set_absolute_axis_data(i_axis_data: tuple) -> None
```

CATIA COM: `o Sub SetAbsoluteAxisData(CATSafeArrayVariant iAxisData)`.

API [Sketch.get_absolute_axis_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.get_absolute_axis_data)

```python
get_absolute_axis_data() -> tuple
```

CATIA COM: `o Sub GetAbsoluteAxisData(CATSafeArrayVariant oAxisData)`.


## Sketcher и исходная геометрия

### 11 Sketch

**CATIA-011 · workflow · P1**

Разрешить Reference на плоскость или плоскую грань; создать Sketch, открыть Factory2D, завершить edition даже при ошибке.

Проверка: Криволинейная грань не является обычной плоской опорой.

API [Sketches.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/sketches.html#pycatia.mec_mod_interfaces.sketches.Sketches.add)

```python
add(i_plane: Reference) -> Sketch
```

CATIA COM: `o Func Add(Reference iPlane) As Sketch`.

API [Sketch.open_edition](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.open_edition)

```python
open_edition() -> Factory2D
```

CATIA COM: `o Func OpenEdition() As Factory2D`.

API [Sketch.close_edition](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.close_edition)

```python
close_edition() -> None
```

CATIA COM: `o Sub CloseEdition()`.


### 12 Positioned Sketch

**CATIA-012 · workflow · P1**

Передать 9 компонент абсолютных осей по документации; проверить начало и ортонормированность. Не заявлять полное воспроизведение UI Positioned Sketch без проверки associativity.

Проверка: Проверь направление H и V после переноса.

API [Sketches.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/sketches.html#pycatia.mec_mod_interfaces.sketches.Sketches.add)

```python
add(i_plane: Reference) -> Sketch
```

CATIA COM: `o Func Add(Reference iPlane) As Sketch`.

API [Sketch.set_absolute_axis_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.set_absolute_axis_data)

```python
set_absolute_axis_data(i_axis_data: tuple) -> None
```

CATIA COM: `o Sub SetAbsoluteAxisData(CATSafeArrayVariant iAxisData)`.


### 13 Point

**CATIA-013 · direct · P1**

Локальные x y эскиза; вернуть Point2D.

Проверка: Задай её положение, а не только нарисуй.

API [Factory2D.create_point](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_point)

```python
create_point(i_x: float, i_y: float) -> Point2D
```

CATIA COM: `o Func CreatePoint(double iX, double iY) As Point2D`.


### 14 Line

**CATIA-014 · direct · P1**

Концы в координатах sketch; проверить ненулевую длину.

Проверка: Проверь совпадение концов соседних отрезков.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.


### 15 Profile

**CATIA-015 · workflow · P1**

Собрать профиль из примитивов и явных связей; замкнутость проверять до solid feature.

Проверка: Контролируй переход между режимами линии и дуги.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 16 Rectangle и Centered Rectangle

**CATIA-016 · workflow · P1**

Четыре линии, общие вершины или coincidence, horizontal vertical и размеры; centered rectangle дополнительно привязать к центру.

Проверка: Нужны размеры и положение, а не только прямые углы.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.


### 17 Circle

**CATIA-017 · direct · P1**

Центр и положительный радиус в координатах sketch.

Проверка: Не перепутай радиус и диаметр.

API [Factory2D.create_closed_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_closed_circle)

```python
create_closed_circle(i_center_x: float, i_center_y: float, i_radius: float) -> Circle2D
```

CATIA COM: `o Func CreateClosedCircle(double iCenterX, double iCenterY, double iRadius) As Circle2D`.


### 18 Arc

**CATIA-018 · direct · P1**

Дуга с начальным и конечным параметрами; проверить единицы углов по Factory2D, направление и неравенство параметров.

Проверка: Для R350 используй дугу, а не произвольный сплайн.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.


### 19 Ellipse

**CATIA-019 · direct · P1**

Оси, центр и параметры дуги; различать полную и частичную эллиптическую кривую.

Проверка: Размеры полуосей и полных осей различаются.

API [Factory2D.create_ellipse](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_ellipse)

```python
create_ellipse(i_center_x: float, i_center_y: float, i_major_x: float, i_major_y: float, i_major_radius: float, i_minor_radius: float, i_start_param: float, i_end_param: float) -> Ellipse2D
```

CATIA COM: `o Func CreateEllipse(double iCenterX, double iCenterY, double iMajorX, double iMajorY, double iMajorRadius, double iMinorRadius, double iStartParam, double iEndParam) As Ellipse2D`.

API [Factory2D.create_closed_ellipse](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_closed_ellipse)

```python
create_closed_ellipse(i_center_x: float, i_center_y: float, i_major_x: float, i_major_y: float, i_major_radius: float, i_minor_radius: float) -> Ellipse2D
```

CATIA COM: `o Func CreateClosedEllipse(double iCenterX, double iCenterY, double iMajorX, double iMajorY, double iMajorRadius, double iMinorRadius) As Ellipse2D`.


### 20 Spline

**CATIA-020 · workflow · P1**

Создать контрольные точки и передать коллекцию в формате wrapper; проверить порядок и замкнутость.

Проверка: Лишние точки часто вызывают волнистость.

API [Factory2D.create_control_point](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_control_point)

```python
create_control_point(i_x: float, i_y: float) -> ControlPoint2D
```

CATIA COM: `o Func CreateControlPoint(double iX, double iY) As ControlPoint2D`.

API [Factory2D.create_spline](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_spline)

```python
create_spline(i_poles: tuple) -> Spline2D
```

CATIA COM: `o Func CreateSpline(CATSafeArrayVariant iPoles) As Spline2D`.


### 21 Axis и Construction Geometry

**CATIA-021 · property · P1**

Construction задаётся свойством геометрии. Ось вращения связывать с нужной линией эскиза; назначение center_line проверить отдельно.

Проверка: Вспомогательные линии исключаются из рабочего профиля.

API [Geometry2D.construction](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/geometry_2D.html#pycatia.sketcher_interfaces.geometry_2D.Geometry2D.construction)

```python
property construction: bool
```

CATIA COM: `o Property Construction() As boolean`.

Свойство имеет setter.

API [Sketch.center_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.center_line)

```python
property center_line: Line2D
```

CATIA COM: `o Property CenterLine() As Line2D`.

Свойство имеет setter.


## Sketcher и редактирование профилей

### 22 Corner

**CATIA-022 · composite · P4**

Прямой Sketcher Corner не подтверждён. Для поддержанных пар линий вычислить касательные точки и создать дугу; обновить концы и constraints. Общий случай не обещать.

Проверка: После скругления проверь размеры прилегающих участков.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 23 Chamfer

**CATIA-023 · composite · P4**

Прямой Sketcher Chamfer не подтверждён. Реализовать ограниченный геометрический алгоритм для двух линий с заданными длинами или углом.

Проверка: Уточни способ задания двух длин или длины и угла.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Line2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/line_2D.html#pycatia.sketcher_interfaces.line_2D.Line2D.set_data)

```python
set_data(i_x: float, i_y: float, i_x_direction: float, i_y_direction: float) -> None
```

CATIA COM: `o Sub SetData(double iX, double iY, double iXDirection, double iYDirection)`.


### 24 Trim и Quick Trim

**CATIA-024 · composite · P4**

Прямой UI Trim не подтверждён; вычислить пересечения и явно выбрать сохраняемые интервалы. Не удалять исходники до проверки замены.

Проверка: Можно случайно разомкнуть рабочий контур.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.

API [Selection.delete](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/selection.html#pycatia.in_interfaces.selection.Selection.delete)

```python
delete() -> None
```

CATIA COM: `o Sub Delete()`.


### 25 Break

**CATIA-025 · composite · P4**

Разбить поддерживаемый тип кривой в параметре; перенести допустимые зависимости. Для spline нужен отдельный алгоритм и тест.

Проверка: Проверь появившиеся концы и связи.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.

API [Selection.delete](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/selection.html#pycatia.in_interfaces.selection.Selection.delete)

```python
delete() -> None
```

CATIA COM: `o Sub Delete()`.


### 26 Mirror

**CATIA-026 · composite · P4**

Отразить поддерживаемые примитивы относительно линии; если нужна ассоциативность, задать симметричные constraints, а не только новые координаты.

Проверка: Выбирай ось замысла, а не случайный край.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Factory2D.create_closed_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_closed_circle)

```python
create_closed_circle(i_center_x: float, i_center_y: float, i_radius: float) -> Circle2D
```

CATIA COM: `o Func CreateClosedCircle(double iCenterX, double iCenterY, double iRadius) As Circle2D`.

API [Constraints.add_tri_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_tri_elt_cst)

```python
add_tri_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference, i_third_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddTriEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem, Reference iThirdElem) As Constraint`.


### 27 Symmetry

**CATIA-027 · composite · P4**

Различить перенос исходной геометрии и создание зеркальной копии; сохранить согласованный граф связей.

Проверка: Проверь режим сохранения исходных элементов.

API [Constraints.add_tri_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_tri_elt_cst)

```python
add_tri_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference, i_third_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddTriEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem, Reference iThirdElem) As Constraint`.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.


### 28 Translate и Rotate

**CATIA-028 · composite · P4**

Выполнить 2D матрицу переноса или вращения для явно поддержанных объектов. Размерные ограничения могут запрещать перемещение.

Проверка: Не замени нужную зависимость случайным перемещением.

API [Point2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/point_2D.html#pycatia.sketcher_interfaces.point_2D.Point2D.set_data)

```python
set_data(i_x: float, i_y: float) -> None
```

CATIA COM: `o Sub SetData(double iX, double iY)`.

API [Line2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/line_2D.html#pycatia.sketcher_interfaces.line_2D.Line2D.set_data)

```python
set_data(i_x: float, i_y: float, i_x_direction: float, i_y_direction: float) -> None
```

CATIA COM: `o Sub SetData(double iX, double iY, double iXDirection, double iYDirection)`.

API [Circle2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/circle_2D.html#pycatia.sketcher_interfaces.circle_2D.Circle2D.set_data)

```python
set_data(i_center_x: float, i_center_y: float, i_radius: float) -> None
```

CATIA COM: `o Sub SetData(double iCenterX, double iCenterY, double iRadius)`.


### 29 Scale

**CATIA-029 · composite · P4**

Масштабировать относительно центра; положительный коэффициент, радиусы и размеры обновлять согласованно.

Проверка: После операции проверь размерные ограничения.

API [Point2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/point_2D.html#pycatia.sketcher_interfaces.point_2D.Point2D.set_data)

```python
set_data(i_x: float, i_y: float) -> None
```

CATIA COM: `o Sub SetData(double iX, double iY)`.

API [Line2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/line_2D.html#pycatia.sketcher_interfaces.line_2D.Line2D.set_data)

```python
set_data(i_x: float, i_y: float, i_x_direction: float, i_y_direction: float) -> None
```

CATIA COM: `o Sub SetData(double iX, double iY, double iXDirection, double iYDirection)`.

API [Circle2D.set_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/circle_2D.html#pycatia.sketcher_interfaces.circle_2D.Circle2D.set_data)

```python
set_data(i_center_x: float, i_center_y: float, i_radius: float) -> None
```

CATIA COM: `o Sub SetData(double iCenterX, double iCenterY, double iRadius)`.


### 30 Offset

**CATIA-030 · composite · P4**

Узкая реализация offset для линий и окружностей с явным знаком; общие профили, соединения и самопересечения требуют отдельной библиотеки геометрии.

Проверка: Малые радиусы могут давать самопересечения.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Factory2D.create_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_circle)

```python
create_circle(i_center_x: float, i_center_y: float, i_radius: float, i_start_param: float, i_end_param: float) -> Circle2D
```

CATIA COM: `o Func CreateCircle(double iCenterX, double iCenterY, double iRadius, double iStartParam, double iEndParam) As Circle2D`.


### 31 Project 3D Elements

**CATIA-031 · direct · P1**

Передать Reference 3D-элемента; проверить число созданных элементов и associativity.

Проверка: Ассоциативная проекция зависит от исходной опоры.

API [Factory2D.create_projection](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_projection)

```python
create_projection(i_geometry: Reference) -> Geometry2D
```

CATIA COM: `o Func CreateProjection(Reference iGeometry) As Geometry2D`.

API [Factory2D.create_projections](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_projections)

```python
create_projections(i_geometry: Reference) -> GeometricElements
```

CATIA COM: `o Func CreateProjections(Reference iGeometry) As GeometricElements`.


### 32 Intersect 3D Elements

**CATIA-032 · direct · P1**

Пересечь поддерживаемый 3D-элемент с плоскостью sketch; обработать пустое или множественное пересечение.

Проверка: Пересечение и проекция дают разные результаты.

API [Factory2D.create_intersection](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_intersection)

```python
create_intersection(i_geometry: Reference) -> Geometry2D
```

CATIA COM: `o Func CreateIntersection(Reference iGeometry) As Geometry2D`.

API [Factory2D.create_intersections](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_intersections)

```python
create_intersections(i_geometry: Reference) -> GeometricElements
```

CATIA COM: `o Func CreateIntersections(Reference iGeometry) As GeometricElements`.


### 33 Sketch Analysis

**CATIA-033 · partial · P1**

Это данные для диагностики; полная эквивалентность окну Sketch Analysis не подтверждена. Дополнительно проверять открытые концы и дубликаты собственным алгоритмом.

Проверка: Нулевой визуальный зазор ещё не доказывает совпадение.

API [Sketch.evaluate](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.evaluate)

```python
evaluate() -> None
```

CATIA COM: `o Sub Evaluate()`.

API [Constraints.broken_constraints_count](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.broken_constraints_count)

```python
property broken_constraints_count: int
```

CATIA COM: `o Property BrokenConstraintsCount() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Constraints.un_updated_constraints_count](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.un_updated_constraints_count)

```python
property un_updated_constraints_count: int
```

CATIA COM: `o Property UnUpdatedConstraintsCount() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


## Ограничения и размерный замысел

### 34 Length и Distance

**CATIA-034 · workflow · P1**

Выбрать CatConstraintType по геометрии; длина одного элемента или расстояние двух. Задать dimension после создания.

Проверка: Проверь: размер горизонтальный, вертикальный или истинный.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Dimension.value](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/real_param.html#pycatia.knowledge_interfaces.real_param.RealParam.value)

```python
property value: float
```

Объявлен в `RealParam.value` и наследуется целевым классом.

CATIA COM: `o Property Value() As double`.

Свойство имеет setter.


### 35 Radius и Diameter

**CATIA-035 · partial · P1**

В CatConstraintType 0.10.1 есть catCstTypeRadius, но отдельный Diameter не найден. Управляющий диаметр реализовать параметром D и формулой R = D / 2; отображение diameter в UI — отдельная неподтверждённая возможность.

Проверка: Указание Ø относится к диаметру, R к радиусу.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Relations.create_formula](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_formula)

```python
create_formula(i_name: str, i_comment: str, i_output_parameter: Parameter, i_formula_body: str)
```

CATIA COM: `o Func CreateFormula(CATBSTR iName, CATBSTR iComment, Parameter iOutputParameter, CATBSTR iFormulaBody) As Formula`.


### 36 Angle

**CATIA-036 · workflow · P1**

Угол между разрешёнными элементами; явно задать ориентацию/сторону где нужно.

Проверка: Острый и дополнительный угол дают разные положения.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 37 Coincidence

**CATIA-037 · direct · P1**

Тип coincidence; ссылки на вершины или геометрию должны соответствовать допустимой комбинации.

Проверка: Близость на экране не заменяет совпадение.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 38 Horizontal и Vertical

**CATIA-038 · direct · P1**

Тип horizontal либо vertical для линии; не подменять Fix.

Проверка: Оси эскиза могут отличаться от глобальных XYZ.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.


### 39 Parallelism и Perpendicularity

**CATIA-039 · direct · P1**

Тип parallelism либо perpendicularity; проверить совместимость с уже существующими связями.

Проверка: Не добавляй дублирующее угловое ограничение.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 40 Tangency

**CATIA-040 · direct · P1**

Тип tangency; допустимые кривые, выбор касания и радиусы должны давать решение.

Проверка: Касание продолжений не всегда означает нужный контакт дуг.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 41 Concentricity

**CATIA-041 · direct · P1**

Тип concentricity; обе геометрии должны иметь осмысленный центр/ось.

Проверка: Равенство радиусов этим не задаётся.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 42 Symmetry

**CATIA-042 · direct · P1**

Тип symmetry и третья опора; порядок трёх Reference важен.

Проверка: Полезнее двух независимых одинаковых размеров.

API [Constraints.add_tri_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_tri_elt_cst)

```python
add_tri_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference, i_third_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddTriEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem, Reference iThirdElem) As Constraint`.


### 43 Equality

**CATIA-043 · composite · P4**

Универсального Equality enum в CatConstraintType 0.10.1 нет. Использовать formula между размерными параметрами; catCstTypeEquidistance применять только к поддерживаемой конфигурации геометрии.

Проверка: Одно управляющее значение проще нескольких копий.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Relations.create_formula](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_formula)

```python
create_formula(i_name: str, i_comment: str, i_output_parameter: Parameter, i_formula_body: str)
```

CATIA COM: `o Func CreateFormula(CATBSTR iName, CATBSTR iComment, Parameter iOutputParameter, CATBSTR iFormulaBody) As Formula`.


### 44 Fix

**CATIA-044 · direct · P1**

Тип reference для фиксированной sketch-геометрии; не смешивать с режимом измерительного размера.

Проверка: Не используй для маскировки неясных привязок.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.


### 45 Driving и Reference Dimension

**CATIA-045 · property · P1**

Переключить CatConstraintMode между driving и driven; значение driven получать как результат, а не насильно изменять.

Проверка: Справочный размер не изменит геометрию.

API [Constraint.mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.mode)

```python
property mode: int
```

CATIA COM: `o Property Mode() As CatConstraintMode`.

Свойство имеет setter.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


## Part Design и основные объёмные операции

### 46 Pad

**CATIA-046 · direct · P1**

Эскиз и длина; текущий Body должен быть определён. Для остальных лимитов настроить Prism и Limit.

Проверка: Проверь контур, направление и соединение с телом.

API [ShapeFactory.add_new_pad](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_pad)

```python
add_new_pad(i_sketch: Sketch, i_height: float) -> Pad
```

CATIA COM: `o Func AddNewPad(Sketch iSketch, double iHeight) As Pad`.

Класс настройки [Pad](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/pad.html#pycatia.part_interfaces.pad.Pad); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 47 Pocket

**CATIA-047 · direct · P1**

Эскиз и глубина; проверить пересечение с целевым solid и уменьшение объёма.

Проверка: Убедись, что направление пересекает материал.

API [ShapeFactory.add_new_pocket](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_pocket)

```python
add_new_pocket(i_sketch: Sketch, i_height: float) -> Pocket
```

CATIA COM: `o Func AddNewPocket(Sketch iSketch, double iHeight) As Pocket`.

Класс настройки [Pocket](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/pocket.html#pycatia.part_interfaces.pocket.Pocket); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 48 Shaft

**CATIA-048 · workflow · P1**

Создать Shaft из профиля, явно назначить ось через Reference, настроить углы. Граница профиля не должна пересекать ось недопустимым образом.

Проверка: Контролируй пересечение профиля с осью.

API [ShapeFactory.add_new_shaft](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_shaft)

```python
add_new_shaft(i_sketch: Sketch) -> Shaft
```

CATIA COM: `o Func AddNewShaft(Sketch iSketch) As Shaft`.

API [Revolution.revolute_axis](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.revolute_axis)

```python
property revolute_axis: Reference
```

CATIA COM: `o Property RevoluteAxis() As Reference`.

Свойство имеет setter.

API [Revolution.first_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.first_angle)

```python
property first_angle: Angle
```

CATIA COM: `o Property FirstAngle() As Angle`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Revolution.second_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.second_angle)

```python
property second_angle: Angle
```

CATIA COM: `o Property SecondAngle() As Angle`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 49 Groove

**CATIA-049 · workflow · P1**

Вращательный вырез с явной осью; проверить удалённый материал.

Проверка: Выбери нужную ось и угол вращения.

API [ShapeFactory.add_new_groove](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_groove)

```python
add_new_groove(i_sketch: Sketch) -> Groove
```

CATIA COM: `o Func AddNewGroove(Sketch iSketch) As Groove`.

API [Revolution.revolute_axis](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.revolute_axis)

```python
property revolute_axis: Reference
```

CATIA COM: `o Property RevoluteAxis() As Reference`.

Свойство имеет setter.

API [Revolution.first_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.first_angle)

```python
property first_angle: Angle
```

CATIA COM: `o Property FirstAngle() As Angle`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Revolution.second_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/revolution.html#pycatia.part_interfaces.revolution.Revolution.second_angle)

```python
property second_angle: Angle
```

CATIA COM: `o Property SecondAngle() As Angle`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 50 Hole

**CATIA-050 · direct · P1**

Выбрать один контракт позиционирования отверстия; не выдавать face плюс depth за достаточные данные его центра.

Проверка: Положение центра и направление задаются отдельно.

API [ShapeFactory.add_new_hole_from_sketch](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_hole_from_sketch)

```python
add_new_hole_from_sketch(i_sketch: Sketch, i_depth: float) -> Hole
```

CATIA COM: `o Func AddNewHoleFromSketch(Sketch iSketch, double iDepth) As Hole`.

API [ShapeFactory.add_new_hole_from_point](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_hole_from_point)

```python
add_new_hole_from_point(i_x: float, i_y: float, i_z: float, i_support: Reference, i_depth: float) -> Hole
```

CATIA COM: `o Func AddNewHoleFromPoint(double iX, double iY, double iZ, Reference iSupport, double iDepth) As Hole`.

API [Hole.diameter](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.diameter)

```python
property diameter: Length
```

CATIA COM: `o Property Diameter() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.bottom_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.bottom_limit)

```python
property bottom_limit: Limit
```

CATIA COM: `o Property BottomLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 51 Rib

**CATIA-051 · direct · P2**

Профиль и центральная кривая; параметры ориентации брать у Sweep, проверить самопересечения.

Проверка: Следи за ориентацией сечения и тесными поворотами.

API [ShapeFactory.add_new_rib](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_rib)

```python
add_new_rib(i_sketch: Sketch, i_center_curve: Sketch) -> Rib
```

CATIA COM: `o Func AddNewRib(Sketch iSketch, Sketch iCenterCurve) As Rib`.

Класс настройки [Rib](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/rib.html#pycatia.part_interfaces.rib.Rib); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 52 Slot

**CATIA-052 · direct · P2**

Профиль и траектория выреза; проверить пересечение с Body.

Проверка: Путь и сечение должны давать допустимый объём.

API [ShapeFactory.add_new_slot](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_slot)

```python
add_new_slot(i_sketch: Sketch, i_center_curve: Sketch) -> Slot
```

CATIA COM: `o Func AddNewSlot(Sketch iSketch, Sketch iCenterCurve) As Slot`.

Класс настройки [Slot](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/slot.html#pycatia.part_interfaces.slot.Slot); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 53 Stiffener

**CATIA-053 · workflow · P2**

Открытый профиль усиливающего ребра и толщина; проверить сопряжение с исходным solid.

Проверка: Проверь сторону материала и связь с опорными стенками.

API [ShapeFactory.add_new_stiffener](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_stiffener)

```python
add_new_stiffener(i_sketch: Sketch) -> Stiffener
```

CATIA COM: `o Func AddNewStiffener(Sketch iSketch) As Stiffener`.

API [Stiffener.thickness](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/stiffener.html#pycatia.part_interfaces.stiffener.Stiffener.thickness)

```python
property thickness: Length
```

CATIA COM: `o Property Thickness() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 54 Multi Sections Solid

**CATIA-054 · workflow · P2**

Создать solid Loft, получить его HybridShape через Loft.hybrid_shape, добавить минимум два сечения, ориентации и направляющие; настроить coupling.

Проверка: Порядок и соответствие точек сечений влияют на скручивание.

API [ShapeFactory.add_new_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_loft)

```python
add_new_loft() -> AnyObject
```

CATIA COM: `o Func AddNewLoft() As AnyObject`.

API [Loft.hybrid_shape](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/loft.html#pycatia.part_interfaces.loft.Loft.hybrid_shape)

```python
property hybrid_shape: HybridShape
```

CATIA COM: `o Property HybridShape() As HybridShape`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [HybridShapeLoft.add_section_to_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_section_to_loft)

```python
add_section_to_loft(i_crv: Reference, i_ori: int, i_point: Union[Reference, VBANothing]) -> None
```

CATIA COM: `o Sub AddSectionToLoft(Reference iCrv, long iOri, Reference iPoint)`.

API [HybridShapeLoft.add_guide](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_guide)

```python
add_guide(i_guide: Reference) -> None
```

CATIA COM: `o Sub AddGuide(Reference iGuide)`.


### 55 Removed Multi Sections Solid

**CATIA-055 · workflow · P2**

Получить Loft.hybrid_shape и настроить loft выреза; проверить пересечение и изменение объёма.

Проверка: Проверь, какие области тела действительно удаляются.

API [ShapeFactory.add_new_removed_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_removed_loft)

```python
add_new_removed_loft() -> AnyObject
```

CATIA COM: `o Func AddNewRemovedLoft() As AnyObject`.

API [Loft.hybrid_shape](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/loft.html#pycatia.part_interfaces.loft.Loft.hybrid_shape)

```python
property hybrid_shape: HybridShape
```

CATIA COM: `o Property HybridShape() As HybridShape`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [HybridShapeLoft.add_section_to_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_section_to_loft)

```python
add_section_to_loft(i_crv: Reference, i_ori: int, i_point: Union[Reference, VBANothing]) -> None
```

CATIA COM: `o Sub AddSectionToLoft(Reference iCrv, long iOri, Reference iPoint)`.

API [HybridShapeLoft.add_guide](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_guide)

```python
add_guide(i_guide: Reference) -> None
```

CATIA COM: `o Sub AddGuide(Reference iGuide)`.


### 56 Multi Pad

**CATIA-056 · unconfirmed · P4**

Прямой Multi Pad в ShapeFactory не найден. Несколько обычных Pad можно предложить как отдельный алгоритм, но это другое feature tree и не эквивалент UI Multi Pad.

Проверка: Профили не должны пересекаться; длина задаётся по областям.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 57 Multi Pocket

**CATIA-057 · unconfirmed · P4**

Прямой Multi Pocket в ShapeFactory не найден. Последовательность Pocket допустима только как явно согласованный заменяющий алгоритм.

Проверка: Не путай с переходом между несколькими сечениями.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


## Границы операций и типы отверстий

### 58 Dimension

**CATIA-058 · property · P2**

Задать размерный режим и dimension. Использовать фактический CatLimitMode из установленного SDK.

Проверка: Проверь единицы и отсчёт от плоскости эскиза.

API [Prism.first_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.first_limit)

```python
property first_limit: Limit
```

CATIA COM: `o Property FirstLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Limit.limit_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.limit_mode)

```python
property limit_mode: int
```

CATIA COM: `o Property LimitMode() As CatLimitMode`.

Свойство имеет setter.

API [Limit.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.dimension)

```python
property dimension: Length
```

CATIA COM: `o Property Dimension() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 59 Up to Next

**CATIA-059 · property · P2**

Режим up to next; проверить, какая грань стала остановкой после Update.

Проверка: Изменение геометрии может сменить эту границу.

API [Prism.first_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.first_limit)

```python
property first_limit: Limit
```

CATIA COM: `o Property FirstLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Limit.limit_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.limit_mode)

```python
property limit_mode: int
```

CATIA COM: `o Property LimitMode() As CatLimitMode`.

Свойство имеет setter.


### 60 Up to Last

**CATIA-060 · property · P2**

Режим up to last; проверить полный диапазон пересекаемого материала.

Проверка: Проверь результат на ступенчатой геометрии.

API [Prism.first_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.first_limit)

```python
property first_limit: Limit
```

CATIA COM: `o Property FirstLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Limit.limit_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.limit_mode)

```python
property limit_mode: int
```

CATIA COM: `o Property LimitMode() As CatLimitMode`.

Свойство имеет setter.


### 61 Up to Plane и Up to Surface

**CATIA-061 · property · P2**

Установить режим и Reference ограничивающей плоскости/поверхности; проверить направление.

Проверка: Опора должна пересекаться с направлением построения.

API [Prism.first_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.first_limit)

```python
property first_limit: Limit
```

CATIA COM: `o Property FirstLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Limit.limit_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.limit_mode)

```python
property limit_mode: int
```

CATIA COM: `o Property LimitMode() As CatLimitMode`.

Свойство имеет setter.

API [Limit.limiting_element](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/limit.html#pycatia.part_interfaces.limit.Limit.limiting_element)

```python
property limiting_element: Reference
```

CATIA COM: `o Property LimitingElement() As Reference`.

Свойство имеет setter.


### 62 Reverse Direction

**CATIA-062 · property · P2**

Явно различать знак направления и назначение другой направляющей.

Проверка: После изменения опоры перепроверь стрелку.

API [Prism.direction_orientation](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.direction_orientation)

```python
property direction_orientation: int
```

CATIA COM: `o Property DirectionOrientation() As CatPrismOrientation`.

Свойство имеет setter.

API [Prism.set_direction](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.set_direction)

```python
set_direction(i_line: Reference) -> None
```

CATIA COM: `o Sub SetDirection(Reference iLine)`.


### 63 Second Limit и Mirrored Extent

**CATIA-063 · property · P2**

Задать второй Limit либо симметричное вытягивание; не считать это отдельным constructor.

Проверка: Доступность и смысл длины зависят от операции.

API [Prism.second_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.second_limit)

```python
property second_limit: Limit
```

CATIA COM: `o Property SecondLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Prism.is_symmetric](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.is_symmetric)

```python
property is_symmetric: bool
```

CATIA COM: `o Property IsSymmetric() As boolean`.

Свойство имеет setter.


### 64 Simple Hole

**CATIA-064 · property · P2**

Выбрать простой тип, диаметр и глубину/условие окончания.

Проверка: Уточни глухое оно или сквозное.

API [Hole.type](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.type)

```python
property type: int
```

CATIA COM: `o Property Type() As CatHoleType`.

Свойство имеет setter.

API [Hole.diameter](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.diameter)

```python
property diameter: Length
```

CATIA COM: `o Property Diameter() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.bottom_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.bottom_limit)

```python
property bottom_limit: Limit
```

CATIA COM: `o Property BottomLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 65 Counterbored Hole

**CATIA-065 · property · P2**

Counterbored: основной диаметр плюс диаметр и глубина расточки.

Проверка: Диаметр и глубина ступени должны соответствовать крепежу.

API [Hole.type](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.type)

```python
property type: int
```

CATIA COM: `o Property Type() As CatHoleType`.

Свойство имеет setter.

API [Hole.head_diameter](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.head_diameter)

```python
property head_diameter: Length
```

CATIA COM: `o Property HeadDiameter() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.head_depth](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.head_depth)

```python
property head_depth: Length
```

CATIA COM: `o Property HeadDepth() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 66 Countersunk Hole

**CATIA-066 · property · P2**

Countersunk: основной диаметр плюс геометрия конической головки.

Проверка: Угол зенковки должен соответствовать головке винта.

API [Hole.type](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.type)

```python
property type: int
```

CATIA COM: `o Property Type() As CatHoleType`.

Свойство имеет setter.

API [Hole.head_diameter](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.head_diameter)

```python
property head_diameter: Length
```

CATIA COM: `o Property HeadDiameter() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.head_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.head_angle)

```python
property head_angle: Angle
```

CATIA COM: `o Property HeadAngle() As Angle`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 67 Threaded Hole и Thread Tap

**CATIA-067 · workflow · P2**

Резьба отверстия и отдельный Thread имеют разные входы. Номинальное обозначение резьбы не гарантирует моделирование витков.

Проверка: Обозначенная резьба не обязательно имеет винтовые 3D-грани.

API [Hole.threading_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.threading_mode)

```python
property threading_mode: int
```

CATIA COM: `o Property ThreadingMode() As CatHoleThreadingMode`.

Свойство имеет setter.

API [Hole.hole_thread_description](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.hole_thread_description)

```python
property hole_thread_description: StrParam
```

CATIA COM: `o Property HoleThreadDescription() As StrParam`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.thread_depth](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.thread_depth)

```python
property thread_depth: Length
```

CATIA COM: `o Property ThreadDepth() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Hole.thread_pitch](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/hole.html#pycatia.part_interfaces.hole.Hole.thread_pitch)

```python
property thread_pitch: Length
```

CATIA COM: `o Property ThreadPitch() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [ShapeFactory.add_new_thread_with_ref](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_thread_with_ref)

```python
add_new_thread_with_ref(i_lateral_face: Reference, i_limit_face: Reference) -> Thread
```

CATIA COM: `o Func AddNewThreadWithRef(Reference iLateralFace, Reference iLimitFace) As Thread`.

API [ShapeFactory.add_new_thread_with_out_ref](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_thread_with_out_ref)

```python
add_new_thread_with_out_ref() -> Thread
```

CATIA COM: `o Func AddNewThreadWithOutRef() As Thread`.


## Скругления стенки и технологическая форма

### 68 Edge Fillet

**CATIA-068 · direct · P2**

Reference на ребро, радиус, propagation enum; добавить остальные рёбра в полученный объект.

Проверка: Слишком большой радиус может пересечь соседние грани.

API [ShapeFactory.add_new_edge_fillet_with_constant_radius](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_edge_fillet_with_constant_radius)

```python
add_new_edge_fillet_with_constant_radius(i_edge_to_fillet: Reference, i_propag_mode: CatFilletEdgePropagation, i_radius: float) -> ConstRadEdgeFillet
```

CATIA COM: `o Func AddNewEdgeFilletWithConstantRadius(Reference iEdgeToFillet, CatFilletEdgePropagation iPropagMode, double iRadius) As ConstRadEdgeFillet`.

API [ConstRadEdgeFillet.add_object_to_fillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/const_rad_edge_fillet.html#pycatia.part_interfaces.const_rad_edge_fillet.ConstRadEdgeFillet.add_object_to_fillet)

```python
add_object_to_fillet(i_object_to_fillet: Reference) -> None
```

CATIA COM: `o Sub AddObjectToFillet(Reference iObjectToFillet)`.


### 69 Variable Radius Fillet

**CATIA-069 · workflow · P2**

Создать feature; задать контрольные точки и радиусы методами возвращённого класса. Требуется отдельный live test для выбранных рёбер.

Проверка: Контролируй переходы и расположение контрольных точек.

API [ShapeFactory.add_new_edge_fillet_with_varying_radius](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_edge_fillet_with_varying_radius)

```python
add_new_edge_fillet_with_varying_radius(i_edge_to_fillet: Reference, i_propag_mode: CatFilletEdgePropagation, i_variation_mode: CatFilletVariation, i_default_radius: float) -> VarRadEdgeFillet
```

CATIA COM: `o Func AddNewEdgeFilletWithVaryingRadius(Reference iEdgeToFillet, CatFilletEdgePropagation iPropagMode, CatFilletVariation iVariationMode, double iDefaultRadius) As VarRadEdgeFillet`.

Класс настройки [VarRadEdgeFillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/var_rad_edge_fillet.html#pycatia.part_interfaces.var_rad_edge_fillet.VarRadEdgeFillet); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 70 Face Face Fillet

**CATIA-070 · direct · P2**

References двух граней, радиус и ориентации по сигнатуре.

Проверка: Проверь сторону и границы полученной поверхности.

API [ShapeFactory.add_new_face_fillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_face_fillet)

```python
add_new_face_fillet(i_f1: Reference, i_f2: Reference, i_radius: float) -> FaceFillet
```

CATIA COM: `o Func AddNewFaceFillet(Reference iF1, Reference iF2, double iRadius) As FaceFillet`.

Класс настройки [FaceFillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/face_fillet.html#pycatia.part_interfaces.face_fillet.FaceFillet); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 71 Tritangent Fillet

**CATIA-071 · direct · P2**

Три грани; проверить, какая грань удаляется и какие стороны сохраняются.

Проверка: Выбор удаляемой средней области критичен.

API [ShapeFactory.add_new_tritangent_fillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_tritangent_fillet)

```python
add_new_tritangent_fillet(i_f1: Reference, i_f2: Reference, i_removed_face: Reference) -> TritangentFillet
```

CATIA COM: `o Func AddNewTritangentFillet(Reference iF1, Reference iF2, Reference iRemovedFace) As TritangentFillet`.

Класс настройки [TritangentFillet](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/tritangent_fillet.html#pycatia.part_interfaces.tritangent_fillet.TritangentFillet); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 72 Chamfer

**CATIA-072 · direct · P2**

Reference, propagation, mode, orientation, размеры либо длина и угол.

Проверка: Фаска и скругление имеют разную функцию.

API [ShapeFactory.add_new_chamfer](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_chamfer)

```python
add_new_chamfer(i_object_to_chamfer: Reference, i_propagation: CatChamferPropagation, i_mode: CatChamferMode, i_orientation: CatChamferOrientation, i_length1: float, i_length2_or_angle: float) -> Chamfer
```

CATIA COM: `o Func AddNewChamfer(Reference iObjectToChamfer, CatChamferPropagation iPropagation, CatChamferMode iMode, CatChamferOrientation iOrientation, double iLength1, double iLength2OrAngle) As Chamfer`.

Класс настройки [Chamfer](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/chamfer.html#pycatia.part_interfaces.chamfer.Chamfer); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 73 Shell

**CATIA-073 · workflow · P2**

Внутренняя/внешняя толщина и удаляемые грани; следить за минимальными радиусами.

Проверка: Малые радиусы могут разрушить внутреннее смещение.

API [ShapeFactory.add_new_shell](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_shell)

```python
add_new_shell(i_face_to_remove: Reference, i_internal_thickness: float, i_external_thickness: float) -> Shell
```

CATIA COM: `o Func AddNewShell(Reference iFaceToRemove, double iInternalThickness, double iExternalThickness) As Shell`.

API [Shell.add_face_to_remove](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shell.html#pycatia.part_interfaces.shell.Shell.add_face_to_remove)

```python
add_face_to_remove(i_face_to_remove: Reference) -> None
```

CATIA COM: `o Sub AddFaceToRemove(Reference iFaceToRemove)`.


### 74 Thickness

**CATIA-074 · direct · P2**

Локальная толщина выбранных граней; не путать с преобразованием открытой поверхности в solid.

Проверка: Проверь знак и сопряжения с соседними гранями.

API [ShapeFactory.add_new_thickness](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_thickness)

```python
add_new_thickness(i_face_to_thicken: Reference, i_offset: float) -> Thickness
```

CATIA COM: `o Func AddNewThickness(Reference iFaceToThicken, double iOffset) As Thickness`.

Класс настройки [Thickness](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/thickness.html#pycatia.part_interfaces.thickness.Thickness); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 75 Draft

**CATIA-075 · workflow · P2**

Передать начальную грань, нейтральную опору, направление, угол и режимы в constructor; получить созданный DraftDomain через item, добавить faces через add_face_to_draft. Коллекция DraftDomains не имеет add.

Проверка: Нейтральная опора определяет неизменяемую область.

API [ShapeFactory.add_new_draft](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_draft)

```python
add_new_draft(i_face_to_draft: Reference, i_neutral: Reference, i_neutral_mode: CatDraftNeutralPropagationMode, i_parting: Reference, i_dir_x: float, i_dir_y: float, i_dir_z: float, i_mode: CatDraftMode, i_angle: float, i_multiselection_mode: CatDraftMultiselectionMode) -> Draft
```

CATIA COM: `o Func AddNewDraft(Reference iFaceToDraft, Reference iNeutral, CatDraftNeutralPropagationMode iNeutralMode, Reference iParting, double iDirX, double iDirY, double iDirZ, CatDraftMode iMode, double iAngle, CatDraftMultiselectionMode iMultiselectionMode) As Draft`.

API [Draft.draft_domains](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/draft.html#pycatia.part_interfaces.draft.Draft.draft_domains)

```python
property draft_domains: DraftDomains
```

CATIA COM: `o Property DraftDomains() As DraftDomains`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DraftDomains.item](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/draft_domains.html#pycatia.part_interfaces.draft_domains.DraftDomains.item)

```python
item(i_index: CATVariant) -> DraftDomain
```

CATIA COM: `o Func Item(CATVariant iIndex) As DraftDomain`.

Класс настройки [DraftDomain](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/draft_domain.html#pycatia.part_interfaces.draft_domain.DraftDomain); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 76 Thick Surface

**CATIA-076 · direct · P2**

Reference на поверхность и две толщины с выбранной ориентацией; проверить знак и самопересечения.

Проверка: Смещение может самопересекаться на сильной кривизне.

API [ShapeFactory.add_new_thick_surface](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_thick_surface)

```python
add_new_thick_surface(i_offset_element: Reference, i_isens_offset: int, i_top_offset: float, i_bot_offset: float) -> ThickSurface
```

CATIA COM: `o Func AddNewThickSurface(Reference iOffsetElement, long iIsensOffset, double iTopOffset, double iBotOffset) As ThickSurface`.

Класс настройки [ThickSurface](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/thick_surface.html#pycatia.part_interfaces.thick_surface.ThickSurface); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 77 Close Surface

**CATIA-077 · direct · P2**

Reference на замкнутую оболочку; Join сам по себе не создаёт solid.

Проверка: Оболочка должна ограничивать корректный объём.

API [ShapeFactory.add_new_close_surface](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_close_surface)

```python
add_new_close_surface(i_close_element: Reference) -> CloseSurface
```

CATIA COM: `o Func AddNewCloseSurface(Reference iCloseElement) As CloseSurface`.


## Повторения преобразования и несколько тел

### 78 Rectangular Pattern

**CATIA-078 · workflow · P2**

Feature, количества, шаги, начальные позиции, две направляющие и ориентации; счёт включает исходный экземпляр согласно API.

Проверка: Не путай шаг между соседями с общей длиной массива.

API [ShapeFactory.add_new_rect_pattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_rect_pattern)

```python
add_new_rect_pattern(i_shape_to_copy: AnyObject, i_nb_of_copies_in_dir1: int, i_nb_of_copies_in_dir2: int, i_step_in_dir1: float, i_step_in_dir2: float, i_shape_to_copy_position_along_dir1: int, i_shape_to_copy_position_along_dir2: int, i_dir1: Reference, i_dir2: Reference, i_is_reversed_dir1: bool, i_is_reversed_dir2: bool, i_rotation_angle: float) -> RectPattern
```

CATIA COM: `o Func AddNewRectPattern(AnyObject iShapeToCopy, long iNbOfCopiesInDir1, long iNbOfCopiesInDir2, double iStepInDir1, double iStepInDir2, long iShapeToCopyPositionAlongDir1, long iShapeToCopyPositionAlongDir2, Reference iDir1, Reference iDir2, boolean iIsReversedDir1, boolean iIsReversedDir2, double iRotationAngle) As RectPattern`.

Класс настройки [RectPattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/rect_pattern.html#pycatia.part_interfaces.rect_pattern.RectPattern); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 79 Circular Pattern

**CATIA-079 · workflow · P2**

Feature, радиальные/угловые параметры, центр и ось; проверить диапазон углов и число instances.

Проверка: Проверь полный круг и отсутствие наложения первого и последнего.

API [ShapeFactory.add_new_circ_pattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_circ_pattern)

```python
add_new_circ_pattern(i_shape_to_copy: AnyObject, i_nb_of_copies_in_radial_dir: int, i_nb_of_copies_in_angular_dir: int, i_step_in_radial_dir: float, i_step_in_angular_dir: float, i_shape_to_copy_position_along_radial_dir: int, i_shape_to_copy_position_along_angular_dir: int, i_rotation_center: Reference, i_rotation_axis: Reference, i_is_reversed_rotation_axis: bool, i_rotation_angle: float, i_is_radius_aligned: bool) -> CircPattern
```

CATIA COM: `o Func AddNewCircPattern(AnyObject iShapeToCopy, long iNbOfCopiesInRadialDir, long iNbOfCopiesInAngularDir, double iStepInRadialDir, double iStepInAngularDir, long iShapeToCopyPositionAlongRadialDir, long iShapeToCopyPositionAlongAngularDir, Reference iRotationCenter, Reference iRotationAxis, boolean iIsReversedRotationAxis, double iRotationAngle, boolean iIsRadiusAligned) As CircPattern`.

Класс настройки [CircPattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/circ_pattern.html#pycatia.part_interfaces.circ_pattern.CircPattern); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 80 User Pattern

**CATIA-080 · workflow · P2**

Feature и размещения; настройку sketch/anchor проверить по возвращённому классу.

Проверка: Проверь, какие точки считаются позициями.

API [ShapeFactory.add_new_user_pattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_user_pattern)

```python
add_new_user_pattern(i_shape_to_copy: AnyObject, i_nb_of_copies: int) -> UserPattern
```

CATIA COM: `o Func AddNewUserPattern(AnyObject iShapeToCopy, long iNbOfCopies) As UserPattern`.

Класс настройки [UserPattern](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/user_pattern.html#pycatia.part_interfaces.user_pattern.UserPattern); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 81 Mirror

**CATIA-081 · direct · P2**

Зеркальная опора; проверить, какой current Body или feature зеркалится.

Проверка: Опора должна отражать реальную симметрию детали.

API [ShapeFactory.add_new_mirror](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_mirror)

```python
add_new_mirror(i_mirroring_element: Reference) -> Mirror
```

CATIA COM: `o Func AddNewMirror(Reference iMirroringElement) As Mirror`.


### 82 Translation и Rotation

**CATIA-082 · workflow · P2**

Назначить направление/ось и величину трансформации свойствами объекта; не смешивать с Move компонента сборки.

Проверка: Это не сборочная зависимость между отдельными деталями.

API [ShapeFactory.add_new_translate2](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_translate2)

```python
add_new_translate2(i_distance: float) -> Translate
```

CATIA COM: `Function AddNewTranslate2(iDistance As Double) As AnyObject`.

Класс настройки [Translate](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/translate.html#pycatia.part_interfaces.translate.Translate); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

API [ShapeFactory.add_new_rotate2](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_rotate2)

```python
add_new_rotate2(i_axis: Reference, i_angle: float) -> AnyObject
```

CATIA COM: `Function AddNewRotate2(iAxis As Reference, iAngle As Double) As AnyObject`.

Класс настройки [Rotate](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/rotate.html#pycatia.part_interfaces.rotate.Rotate); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 83 Scaling и Affinity

**CATIA-083 · direct · P2**

Scaling использует опору и коэффициент; Affinity независимые коэффициенты x y z. Проверить выходные размеры.

Проверка: Радиусы, отверстия и толщины также изменяются.

API [ShapeFactory.add_new_scaling](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_scaling)

```python
add_new_scaling(i_scaling_reference: Reference, i_factor: float) -> Scaling
```

CATIA COM: `o Func AddNewScaling(Reference iScalingReference, double iFactor) As Scaling`.

API [ShapeFactory.add_new_affinity2](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_affinity2)

```python
add_new_affinity2(x_ratio: float, y_ratio: float, z_ratio: float) -> AnyObject
```

CATIA COM: `o Func AddNewAffinity2(double XRatio, double YRatio, double ZRatio) As AnyObject`.


### 84 Boolean Add

**CATIA-084 · direct · P2**

Body-операнд и текущий target Body; проверить оба контекста.

Проверка: Проверь допустимость результата для выбранного Body.

API [ShapeFactory.add_new_add](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_add)

```python
add_new_add(i_body_to_add: Body) -> Add
```

CATIA COM: `o Func AddNewAdd(Body iBodyToAdd) As Add`.


### 85 Boolean Remove

**CATIA-085 · direct · P2**

Вычесть operand Body из текущего Body; не удалять operand вручную.

Проверка: Полезно хранить вычитающий инструмент как понятное тело.

API [ShapeFactory.add_new_remove](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_remove)

```python
add_new_remove(i_body_to_remove: Body) -> Remove
```

CATIA COM: `o Func AddNewRemove(Body iBodyToRemove) As Remove`.


### 86 Boolean Intersect

**CATIA-086 · direct · P2**

Пересечение двух тел; проверить непустой результат.

Проверка: Без пересечения нужного объёма не получится.

API [ShapeFactory.add_new_intersect](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_intersect)

```python
add_new_intersect(i_body_to_intersect: Body) -> Intersect
```

CATIA COM: `o Func AddNewIntersect(Body iBodyToIntersect) As Intersect`.


### 87 Boolean Assemble

**CATIA-087 · direct · P2**

Assembly boolean внутри Part, не добавление компонента CATProduct; учитывает тип/историю operand.

Проверка: Не считай универсальным синонимом Add.

API [ShapeFactory.add_new_assemble](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_assemble)

```python
add_new_assemble(i_body_to_assemble: Body) -> Assemble
```

CATIA COM: `o Func AddNewAssemble(Body iBodyToAssemble) As Assemble`.


### 88 Split Solid

**CATIA-088 · direct · P2**

Опорная поверхность и сторона сохранения; проверить оставшийся solid.

Проверка: Всегда проверяй сохраняемую сторону в Preview.

API [ShapeFactory.add_new_split](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_split)

```python
add_new_split(i_splitting_element: Reference, i_split_side: CatSplitSide) -> Split
```

CATIA COM: `o Func AddNewSplit(Reference iSplittingElement, CatSplitSide iSplitSide) As Split`.


## Опорные точки линии и системы координат

### 89 Point Coordinates

**CATIA-089 · direct · P1**

Координаты относительно текущей системы; для другой системы настроить RefAxisSystem у точки.

Проверка: Проверь, какая система активна.

API [HybridShapeFactory.add_new_point_coord](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_coord)

```python
add_new_point_coord(i_x: float, i_y: float, i_z: float) -> HybridShapePointCoord
```

CATIA COM: `o Func AddNewPointCoord(double iX, double iY, double iZ) As HybridShapePointCoord`.


### 90 Point On Curve

**CATIA-090 · direct · P1**

Выбрать fraction либо distance и направление; 0.5 не считать центром всей детали.

Проверка: Ratio 0,5 относится к выбранному участку кривой.

API [HybridShapeFactory.add_new_point_on_curve_from_percent](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_curve_from_percent)

```python
add_new_point_on_curve_from_percent(i_crv: Reference, i_long: float, i_orientation: bool) -> HybridShapePointOnCurve
```

CATIA COM: `o Func AddNewPointOnCurveFromPercent(Reference iCrv, double iLong, boolean iOrientation) As HybridShapePointOnCurve`.

API [HybridShapeFactory.add_new_point_on_curve_from_distance](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_curve_from_distance)

```python
add_new_point_on_curve_from_distance(i_crv: Reference, i_long: float, i_orientation: bool) -> HybridShapePointOnCurve
```

CATIA COM: `o Func AddNewPointOnCurveFromDistance(Reference iCrv, double iLong, boolean iOrientation) As HybridShapePointOnCurve`.

API [HybridShapeFactory.add_new_point_on_curve_with_reference_from_percent](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_curve_with_reference_from_percent)

```python
add_new_point_on_curve_with_reference_from_percent(i_crv: Reference, i_pt: Reference, i_long: float, i_orientation: bool) -> HybridShapePointOnCurve
```

CATIA COM: `o Func AddNewPointOnCurveWithReferenceFromPercent(Reference iCrv, Reference iPt, double iLong, boolean iOrientation) As HybridShapePointOnCurve`.


### 91 Point On Plane

**CATIA-091 · direct · P1**

Reference плоскости, локальные координаты и при необходимости опорная точка.

Проверка: Начало плоскости не обязано совпадать с началом детали.

API [HybridShapeFactory.add_new_point_on_plane](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_plane)

```python
add_new_point_on_plane(i_plane: Reference, i_x: float, i_y: float) -> HybridShapePointOnPlane
```

CATIA COM: `o Func AddNewPointOnPlane(Reference iPlane, double iX, double iY) As HybridShapePointOnPlane`.

API [HybridShapeFactory.add_new_point_on_plane_with_reference](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_plane_with_reference)

```python
add_new_point_on_plane_with_reference(i_plane: Reference, i_pt: Reference, i_x: float, i_y: float) -> HybridShapePointOnPlane
```

CATIA COM: `o Func AddNewPointOnPlaneWithReference(Reference iPlane, Reference iPt, double iX, double iY) As HybridShapePointOnPlane`.


### 92 Point On Surface

**CATIA-092 · direct · P1**

API требует surface, direction и расстояние, а не универсальные u v. Для центра детали использовать геометрические условия и intersection.

Проверка: Default Middle не гарантирует центр сложной обрезанной грани.

API [HybridShapeFactory.add_new_point_on_surface](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_surface)

```python
add_new_point_on_surface(i_surface: Reference, i_direction: HybridShapeDirection, i_x: float) -> HybridShapePointOnSurface
```

CATIA COM: `o Func AddNewPointOnSurface(Reference iSurface, HybridShapeDirection iDirection, double iX) As HybridShapePointOnSurface`.

API [HybridShapeFactory.add_new_point_on_surface_with_reference](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_on_surface_with_reference)

```python
add_new_point_on_surface_with_reference(i_surface: Reference, i_pt: Reference, i_direction: HybridShapeDirection, i_x: float) -> HybridShapePointOnSurface
```

CATIA COM: `o Func AddNewPointOnSurfaceWithReference(Reference iSurface, Reference iPt, HybridShapeDirection iDirection, double iX) As HybridShapePointOnSurface`.


### 93 Circle Sphere Center

**CATIA-093 · direct · P1**

Центр поддерживаемого геометрического объекта; у произвольной поверхности такого универсального центра нет.

Проверка: Центр дуги обычно не лежит на самой дуге.

API [HybridShapeFactory.add_new_point_center](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_center)

```python
add_new_point_center(i_curve: Reference) -> HybridShapePointCenter
```

CATIA COM: `o Func AddNewPointCenter(Reference iCurve) As HybridShapePointCenter`.


### 94 Point Between

**CATIA-094 · direct · P1**

Две точки, ratio и orientation; подтвердить положение при ratio 0.5.

Проверка: Середина хорды не равна середине дуги.

API [HybridShapeFactory.add_new_point_between](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_point_between)

```python
add_new_point_between(i_point1: Reference, i_point2: Reference, i_ratio: float, i_orientation: int) -> HybridShapePointBetween
```

CATIA COM: `o Func AddNewPointBetween(Reference iPoint1, Reference iPoint2, double iRatio, long iOrientation) As HybridShapePointBetween`.


### 95 Line Point Point

**CATIA-095 · direct · P1**

Две разные точки; геометрические References того же документа.

Проверка: Совпадающие точки не задают направление.

API [HybridShapeFactory.add_new_line_pt_pt](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_line_pt_pt)

```python
add_new_line_pt_pt(i_pt_origine: Reference, i_pt_extremite: Reference) -> HybridShapeLinePtPt
```

CATIA COM: `o Func AddNewLinePtPt(Reference iPtOrigine, Reference iPtExtremite) As HybridShapeLinePtPt`.


### 96 Line Point Direction

**CATIA-096 · direct · P1**

Точка, ненулевое направление, начальное и конечное смещения, orientation.

Проверка: Задай нужную длину и ориентацию.

API [HybridShapeFactory.add_new_direction_by_coord](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_direction_by_coord)

```python
add_new_direction_by_coord(i_x: float, i_y: float, i_z: float) -> HybridShapeDirection
```

CATIA COM: `o Func AddNewDirectionByCoord(double iX, double iY, double iZ) As HybridShapeDirection`.

API [HybridShapeFactory.add_new_line_pt_dir](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_line_pt_dir)

```python
add_new_line_pt_dir(i_pt: Reference, i_direction: HybridShapeDirection, i_begin_offset: float, i_end_offset: float, i_orientation: bool) -> HybridShapeLinePtDir
```

CATIA COM: `o Func AddNewLinePtDir(Reference iPt, HybridShapeDirection iDirection, double iBeginOffset, double iEndOffset, boolean iOrientation) As HybridShapeLinePtDir`.


### 97 Line Normal to Surface

**CATIA-097 · direct · P1**

Поверхность, точка на ней, пределы и ориентация; проверить нормаль в данной точке.

Проверка: На ребре между гранями нормаль неоднозначна.

API [HybridShapeFactory.add_new_line_normal](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_line_normal)

```python
add_new_line_normal(i_surface: Reference, i_point: Reference, i_begin_offset: float, i_end_offset: float, i_orientation: bool) -> HybridShapeLineNormal
```

CATIA COM: `o Func AddNewLineNormal(Reference iSurface, Reference iPoint, double iBeginOffset, double iEndOffset, boolean iOrientation) As HybridShapeLineNormal`.


### 98 Line Tangent to Curve

**CATIA-098 · direct · P1**

Кривая, точка, пределы и ориентация; точка должна лежать на кривой.

Проверка: Не перепутай касательную с нормалью.

API [HybridShapeFactory.add_new_line_tangency](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_line_tangency)

```python
add_new_line_tangency(i_curve: Reference, i_point: Reference, i_begin_offset: float, i_end_offset: float, i_orientation: bool) -> HybridShapeLineTangency
```

CATIA COM: `o Func AddNewLineTangency(Reference iCurve, Reference iPoint, double iBeginOffset, double iEndOffset, boolean iOrientation) As HybridShapeLineTangency`.


### 99 Axis System

**CATIA-099 · workflow · P1**

Задать начало и независимые направления; проверить правую систему и ортонормированность.

Проверка: Фиксируй смысл осей и правую ориентацию.

API [AxisSystems.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/axis_systems.html#pycatia.mec_mod_interfaces.axis_systems.AxisSystems.add)

```python
add() -> AxisSystem
```

CATIA COM: `o Func Add() As AxisSystem`.

API [AxisSystem.put_origin](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/axis_system.html#pycatia.mec_mod_interfaces.axis_system.AxisSystem.put_origin)

```python
put_origin(i_origin: tuple) -> None
```

CATIA COM: `o Sub PutOrigin(CATSafeArrayVariant iOrigin)`.

API [AxisSystem.put_vectors](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/axis_system.html#pycatia.mec_mod_interfaces.axis_system.AxisSystem.put_vectors)

```python
put_vectors(i_vector_x: tuple, i_vector_y: tuple) -> None
```

CATIA COM: `o Sub PutVectors(CATSafeArrayVariant iVectorX, CATSafeArrayVariant iVectorY)`.


## Опорные плоскости

### 100 Offset from Plane

**CATIA-100 · direct · P1**

Плоскость, расстояние, orientation.

Проверка: Проверь знак смещения и направление нормали.

API [HybridShapeFactory.add_new_plane_offset](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_offset)

```python
add_new_plane_offset(i_plane: Reference, i_offset: float, i_orientation: bool) -> HybridShapePlaneOffset
```

CATIA COM: `o Func AddNewPlaneOffset(Reference iPlane, double iOffset, boolean iOrientation) As HybridShapePlaneOffset`.


### 101 Parallel through Point

**CATIA-101 · direct · P1**

Плоскость и точка; проверить параллельность и прохождение через точку.

Проверка: Точка управляет положением, исходная плоскость — ориентацией.

API [HybridShapeFactory.add_new_plane_offset_pt](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_offset_pt)

```python
add_new_plane_offset_pt(i_plane: Reference, i_pt: Reference) -> HybridShapePlaneOffsetPt
```

CATIA COM: `o Func AddNewPlaneOffsetPt(Reference iPlane, Reference iPt) As HybridShapePlaneOffsetPt`.


### 102 Angle to Plane

**CATIA-102 · direct · P1**

Плоскость, ось поворота, угол, orientation.

Проверка: Без оси угол не определяет единственную плоскость.

API [HybridShapeFactory.add_new_plane_angle](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_angle)

```python
add_new_plane_angle(i_plane: Reference, i_revol_axis: Reference, i_angle: float, i_orientation: bool) -> HybridShapePlaneAngle
```

CATIA COM: `o Func AddNewPlaneAngle(Reference iPlane, Reference iRevolAxis, double iAngle, boolean iOrientation) As HybridShapePlaneAngle`.


### 103 Through Three Points

**CATIA-103 · direct · P1**

Три неколлинеарные точки.

Проверка: Точки не должны лежать на одной прямой.

API [HybridShapeFactory.add_new_plane3_points](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane3_points)

```python
add_new_plane3_points(i_pt1: Reference, i_pt2: Reference, i_pt3: Reference) -> HybridShapePlane3Points
```

CATIA COM: `o Func AddNewPlane3Points(Reference iPt1, Reference iPt2, Reference iPt3) As HybridShapePlane3Points`.


### 104 Through Two Lines

**CATIA-104 · direct · P1**

Две линии должны задавать плоскость; скрещивающиеся прямые отвергать.

Проверка: Для скрещивающихся прямых уточни используемый режим.

API [HybridShapeFactory.add_new_plane2_lines](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane2_lines)

```python
add_new_plane2_lines(i_ln1: Reference, i_ln2: Reference) -> HybridShapePlane2Lines
```

CATIA COM: `o Func AddNewPlane2Lines(Reference iLn1, Reference iLn2) As HybridShapePlane2Lines`.


### 105 Through Point and Line

**CATIA-105 · direct · P1**

Линия и точка вне неё; вырожденный случай требует другой опоры.

Проверка: Точка на линии не определяет единственную плоскость.

API [HybridShapeFactory.add_new_plane1_line1_pt](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane1_line1_pt)

```python
add_new_plane1_line1_pt(i_ln: Reference, i_pt: Reference) -> HybridShapePlane1Line1Pt
```

CATIA COM: `o Func AddNewPlane1Line1Pt(Reference iLn, Reference iPt) As HybridShapePlane1Line1Pt`.


### 106 Through Planar Curve

**CATIA-106 · direct · P1**

Кривая должна быть плоской.

Проверка: Пространственный сплайн может быть неплоским.

API [HybridShapeFactory.add_new_plane1_curve](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane1_curve)

```python
add_new_plane1_curve(i_planar_curve: Reference) -> HybridShapePlane1Curve
```

CATIA COM: `o Func AddNewPlane1Curve(Reference iPlanarCurve) As HybridShapePlane1Curve`.


### 107 Normal to Curve

**CATIA-107 · direct · P1**

Кривая и точка, задающие локальную нормальную плоскость.

Проверка: Нужна определённая касательная в выбранном месте.

API [HybridShapeFactory.add_new_plane_normal](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_normal)

```python
add_new_plane_normal(i_curve: Reference, i_pt: Reference) -> HybridShapePlaneNormal
```

CATIA COM: `o Func AddNewPlaneNormal(Reference iCurve, Reference iPt) As HybridShapePlaneNormal`.


### 108 Tangent to Surface

**CATIA-108 · direct · P1**

Reference surface и Reference point. Точка на поверхности; центр определяется отдельной операцией.

Проверка: Проверь точку и выбранную грань, особенно у скруглений.

API [HybridShapeFactory.add_new_plane_tangent](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_tangent)

```python
add_new_plane_tangent(i_surface: Reference, i_pt: Reference) -> HybridShapePlaneTangent
```

CATIA COM: `o Func AddNewPlaneTangent(Reference iSurface, Reference iPt) As HybridShapePlaneTangent`.


### 109 Equation

**CATIA-109 · direct · P1**

Коэффициенты уравнения; нормаль ненулевая, единицы свободного члена согласованы с координатами.

Проверка: Коэффициенты относятся к определённой системе координат.

API [HybridShapeFactory.add_new_plane_equation](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_equation)

```python
add_new_plane_equation(i_a_coeff: float, i_b_coeff: float, i_c_coeff: float, i_d_coeff: float) -> HybridShapePlaneEquation
```

CATIA COM: `o Func AddNewPlaneEquation(double iA_Coeff, double iB_Coeff, double iC_Coeff, double iD_Coeff) As HybridShapePlaneEquation`.


### 110 Mean through Points

**CATIA-110 · direct · P1**

Массив References точек и число точек; least squares plane не равна плоскости симметрии.

Проверка: Это приближение; оцени отклонения точек от плоскости.

API [HybridShapeFactory.add_new_plane_mean](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_plane_mean)

```python
add_new_plane_mean(i_list_of_points: tuple, nb_point: int) -> HybridShapePlaneMean
```

CATIA COM: `o Func AddNewPlaneMean(CATSafeArrayVariant iListOfPoints, long NbPoint) As HybridShapePlaneMean`.


## Поверхности и создание внешней формы

### 111 Extrude Surface

**CATIA-111 · direct · P2**

Профиль, начальная и конечная длина, HybridShapeDirection; открытый профиль создаёт поверхность.

Проверка: Замкнутый исходный профиль ещё не делает результат solid.

API [HybridShapeFactory.add_new_extrude](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_extrude)

```python
add_new_extrude(i_object_to_extrude: Reference, i_offset_debut: float, i_offset_fin: float, i_direction: HybridShapeDirection) -> HybridShapeExtrude
```

CATIA COM: `o Func AddNewExtrude(Reference iObjectToExtrude, double iOffsetDebut, double iOffsetFin, HybridShapeDirection iDirection) As HybridShapeExtrude`.


### 112 Revolution Surface

**CATIA-112 · direct · P2**

Профиль, начальный/конечный угол и Reference оси. Не использовать сигнатуру Shaft вместо Revol.

Проверка: Контролируй угол, положение оси и полюса.

API [HybridShapeFactory.add_new_revol](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_revol)

```python
add_new_revol(i_object_to_extrude: Reference, i_offset_debut: float, i_offset_fin: float, i_axis: Reference) -> HybridShapeRevol
```

CATIA COM: `o Func AddNewRevol(Reference iObjectToExtrude, double iOffsetDebut, double iOffsetFin, Reference iAxis) As HybridShapeRevol`.


### 113 Sweep

**CATIA-113 · workflow · P2**

Выбрать тип sweep; назначить spine/guide и параметры возвращённого типа. Один универсальный sweep без mode неоднозначен.

Проверка: Направляющая сама не определяет ориентацию сечения во всех случаях.

API [HybridShapeFactory.add_new_sweep_explicit](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_sweep_explicit)

```python
add_new_sweep_explicit(i_profile: Reference, i_guide: Reference) -> HybridShapeSweepExplicit
```

CATIA COM: `o Func AddNewSweepExplicit(Reference iProfile, Reference iGuide) As HybridShapeSweepExplicit`.

Класс настройки [HybridShapeSweepExplicit](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_sweep_explicit.html#pycatia.hybrid_shape_interfaces.hybrid_shape_sweep_explicit.HybridShapeSweepExplicit); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

API [HybridShapeFactory.add_new_sweep_circle](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_sweep_circle)

```python
add_new_sweep_circle(i_guide1: Reference) -> HybridShapeSweepCircle
```

CATIA COM: `o Func AddNewSweepCircle(Reference iGuide1) As HybridShapeSweepCircle`.

API [HybridShapeFactory.add_new_sweep_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_sweep_line)

```python
add_new_sweep_line(i_guide1: Reference) -> HybridShapeSweepLine
```

CATIA COM: `o Func AddNewSweepLine(Reference iGuide1) As HybridShapeSweepLine`.


### 114 Multi Sections Surface

**CATIA-114 · workflow · P2**

Сечения, ориентации и closing points; направляющие должны пересекать нужные сечения.

Проверка: Проверь направление обхода и точки замыкания сечений.

API [HybridShapeFactory.add_new_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_loft)

```python
add_new_loft() -> HybridShapeLoft
```

CATIA COM: `o Func AddNewLoft() As HybridShapeLoft`.

API [HybridShapeLoft.add_section_to_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_section_to_loft)

```python
add_section_to_loft(i_crv: Reference, i_ori: int, i_point: Union[Reference, VBANothing]) -> None
```

CATIA COM: `o Sub AddSectionToLoft(Reference iCrv, long iOri, Reference iPoint)`.

API [HybridShapeLoft.add_guide](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.add_guide)

```python
add_guide(i_guide: Reference) -> None
```

CATIA COM: `o Sub AddGuide(Reference iGuide)`.

API [HybridShapeLoft.section_coupling](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.section_coupling)

```python
property section_coupling: int
```

CATIA COM: `o Property SectionCoupling() As long`.

Свойство имеет setter.


### 115 Fill

**CATIA-115 · workflow · P2**

Границы образуют замкнутый контур; G1/G2 требуют опор и совместимой геометрии.

Проверка: Слишком противоречивые условия могут искривить внутреннюю область.

API [HybridShapeFactory.add_new_fill](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_fill)

```python
add_new_fill() -> HybridShapeFill
```

CATIA COM: `o Func AddNewFill() As HybridShapeFill`.

API [HybridShapeFill.add_bound](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_fill.html#pycatia.hybrid_shape_interfaces.hybrid_shape_fill.HybridShapeFill.add_bound)

```python
add_bound(i_boundary: Reference) -> None
```

CATIA COM: `o Sub AddBound(Reference iBoundary)`.

API [HybridShapeFill.add_support_at_bound](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_fill.html#pycatia.hybrid_shape_interfaces.hybrid_shape_fill.HybridShapeFill.add_support_at_bound)

```python
add_support_at_bound(i_boundary: Reference, i_support: Reference) -> None
```

CATIA COM: `o Sub AddSupportAtBound(Reference iBoundary, Reference iSupport)`.

API [HybridShapeFill.continuity](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_fill.html#pycatia.hybrid_shape_interfaces.hybrid_shape_fill.HybridShapeFill.continuity)

```python
property continuity: int
```

CATIA COM: `o Property Continuity() As long`.

Свойство имеет setter.


### 116 Blend

**CATIA-116 · workflow · P2**

Настроить обе стороны, направления и условия непрерывности; проверить ориентации.

Проверка: Выбирай требования к касанию исходя из функции перехода.

API [HybridShapeFactory.add_new_blend](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_blend)

```python
add_new_blend() -> HybridShapeBlend
```

CATIA COM: `o Func AddNewBlend() As HybridShapeBlend`.

API [HybridShapeBlend.set_curve](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_blend.html#pycatia.hybrid_shape_interfaces.hybrid_shape_blend.HybridShapeBlend.set_curve)

```python
set_curve(i_blend_limit: int, i_curve: Reference) -> None
```

CATIA COM: `o Sub SetCurve(long iBlendLimit, Reference iCurve)`.

API [HybridShapeBlend.set_support](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_blend.html#pycatia.hybrid_shape_interfaces.hybrid_shape_blend.HybridShapeBlend.set_support)

```python
set_support(i_blend_limit: int, i_support: Reference) -> None
```

CATIA COM: `o Sub SetSupport(long iBlendLimit, Reference iSupport)`.

API [HybridShapeBlend.set_continuity](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_blend.html#pycatia.hybrid_shape_interfaces.hybrid_shape_blend.HybridShapeBlend.set_continuity)

```python
set_continuity(i_blend_limit: int, i_continuity: int) -> None
```

CATIA COM: `o Sub SetContinuity(long iBlendLimit, long iContinuity)`.


### 117 Offset Surface

**CATIA-117 · direct · P2**

Поверхность, offset, orientation и tolerance; проверить складки и самопересечения.

Проверка: На тесных радиусах возможны вырождение и самопересечение.

API [HybridShapeFactory.add_new_offset](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_offset)

```python
add_new_offset(i_object_to_offset: Reference, i_offset: float, i_orientation: bool, i_precision: float) -> HybridShapeOffset
```

CATIA COM: `o Func AddNewOffset(Reference iObjectToOffset, double iOffset, boolean iOrientation, double iPrecision) As HybridShapeOffset`.


### 118 Cylinder и Sphere

**CATIA-118 · direct · P2**

Создать аналитическую поверхность по центру/оси, радиусу и угловым или линейным границам.

Проверка: Это поверхности, а не автоматически замкнутые тела.

API [HybridShapeFactory.add_new_cylinder](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_cylinder)

```python
add_new_cylinder(i_center: Reference, i_radius: float, i_first_length: float, i_second_length: float, i_direction: HybridShapeDirection) -> HybridShapeCylinder
```

CATIA COM: `o Func AddNewCylinder(Reference iCenter, double iRadius, double iFirstLength, double iSecondLength, HybridShapeDirection iDirection) As HybridShapeCylinder`.

API [HybridShapeFactory.add_new_sphere](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_sphere)

```python
add_new_sphere(i_center: Reference, i_axis: Union[Reference, VBANothing], i_radius: float, i_begin_parallel_angle: float, i_end_parallel_angle: float, i_begin_meridian_angle: float, i_end_meridian_angle: float) -> HybridShapeSphere
```

CATIA COM: `o Func AddNewSphere(Reference iCenter, Reference iAxis, double iRadius, double iBeginParallelAngle, double iEndParallelAngle, double iBeginMeridianAngle, double iEndMeridianAngle) As HybridShapeSphere`.


### 119 Helix

**CATIA-119 · direct · P2**

Ось, начальная точка, pitch, height, direction и угловые параметры; учитывать размерности каждого аргумента.

Проверка: Нужна для реальной винтовой геометрии, но увеличивает сложность.

API [HybridShapeFactory.add_new_helix](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_helix)

```python
add_new_helix(i_axis: Reference, i_invert_axis: bool, i_starting_point: Reference, i_pitch: float, i_height: float, i_clockwise_revolution: bool, i_starting_angle: float, i_taper_angle: float, i_taper_outward: bool) -> HybridShapeHelix
```

CATIA COM: `o Func AddNewHelix(Reference iAxis, boolean iInvertAxis, Reference iStartingPoint, double iPitch, double iHeight, boolean iClockwiseRevolution, double iStartingAngle, double iTaperAngle, boolean iTaperOutward) As HybridShapeHelix`.


### 120 Law driven geometry

**CATIA-120 · workflow · P2**

Закон — объект/зависимость для конкретного потребителя; нужен отдельно поддержанный sweep или другой feature с law input.

Проверка: Проверь единицы, диапазон аргумента и гладкость закона.

API [HybridShapeFactory.add_new_integrated_law](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_integrated_law)

```python
add_new_integrated_law(i_type: int) -> HybridShapeIntegratedLaw
```

CATIA COM: `o Func AddNewIntegratedLaw(long iType) As HybridShapeIntegratedLaw`.

API [HybridShapeFactory.add_new_law_dist_proj](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_law_dist_proj)

```python
add_new_law_dist_proj(i_reference: Reference, i_definition: Reference) -> HybridShapeLawDistProj
```

CATIA COM: `o Func AddNewLawDistProj(Reference iReference, Reference iDefinition) As HybridShapeLawDistProj`.

API [Relations.create_law](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_law)

```python
create_law(i_name: str, i_comment: str, i_law_body: str) -> Law
```

CATIA COM: `o Func CreateLaw(CATBSTR iName, CATBSTR iComment, CATBSTR iLawBody) As Law`.


## Поверхности и операции над геометрией

### 121 Extract

**CATIA-121 · direct · P2**

Reference исходника, propagation и при необходимости несколько элементов; проверить результирующую размерность.

Проверка: Извлечённая грань может сохранять связь с исходным телом.

API [HybridShapeFactory.add_new_extract](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_extract)

```python
add_new_extract(element: Reference) -> HybridShapeExtract
```

CATIA COM: `o Func AddNewExtract(Reference Element) As HybridShapeExtract`.

API [HybridShapeExtract.propagation_type](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_extract.html#pycatia.hybrid_shape_interfaces.hybrid_shape_extract.HybridShapeExtract.propagation_type)

```python
property propagation_type: int
```

CATIA COM: `o Property PropagationType() As long`.

Свойство имеет setter.

API [HybridShapeFactory.add_new_extract_multi](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_extract_multi)

```python
add_new_extract_multi(element: Reference) -> HybridShapeExtractMulti
```

CATIA COM: `o Func AddNewExtractMulti(Reference Element) As HybridShapeExtractMulti`.


### 122 Boundary

**CATIA-122 · direct · P2**

Граница поверхности либо ограниченный boundary; несколько контуров вернуть явно.

Проверка: Внутренние отверстия также образуют границы.

API [HybridShapeFactory.add_new_boundary_of_surface](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_boundary_of_surface)

```python
add_new_boundary_of_surface(surface: Reference) -> HybridShapeBoundary
```

CATIA COM: `o Func AddNewBoundaryOfSurface(Reference Surface) As HybridShapeBoundary`.

API [HybridShapeFactory.add_new_boundary](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_boundary)

```python
add_new_boundary(i_initial_element: Reference, i_support: Reference, i_typede_propagation: int) -> HybridShapeBoundary
```

CATIA COM: `o Func AddNewBoundary(Reference iInitialElement, Reference iSupport, long iTypedePropagation) As HybridShapeBoundary`.


### 123 Join

**CATIA-123 · workflow · P2**

Создать Join из двух, добавить остальные; задать допустимую погрешность и проверки связности.

Проверка: Join не гарантирует касательность, замкнутость и наличие объёма.

API [HybridShapeFactory.add_new_join](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_join)

```python
add_new_join(element1: Reference, element2: Reference) -> HybridShapeAssemble
```

CATIA COM: `o Func AddNewJoin(Reference Element1, Reference Element2) As HybridShapeAssemble`.

API [HybridShapeAssemble.add_element](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_assemble.html#pycatia.hybrid_shape_interfaces.hybrid_shape_assemble.HybridShapeAssemble.add_element)

```python
add_element(i_element: Reference) -> None
```

CATIA COM: `o Sub AddElement(Reference iElement)`.

API [HybridShapeAssemble.set_connex](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_assemble.html#pycatia.hybrid_shape_interfaces.hybrid_shape_assemble.HybridShapeAssemble.set_connex)

```python
set_connex(i_connex: bool) -> None
```

CATIA COM: `o Sub SetConnex(boolean iConnex)`.

API [HybridShapeAssemble.set_manifold](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_assemble.html#pycatia.hybrid_shape_interfaces.hybrid_shape_assemble.HybridShapeAssemble.set_manifold)

```python
set_manifold(i_manifold: bool) -> None
```

CATIA COM: `o Sub SetManifold(boolean iManifold)`.

API [HybridShapeAssemble.set_deviation](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_assemble.html#pycatia.hybrid_shape_interfaces.hybrid_shape_assemble.HybridShapeAssemble.set_deviation)

```python
set_deviation(ideviation: float) -> None
```

CATIA COM: `o Sub SetDeviation(double ideviation)`.


### 124 Split Surface

**CATIA-124 · direct · P2**

Исходный элемент, режущий элемент, сторона; подтвердить, какой фрагмент сохранён.

Проверка: Проверь сохраняемую сторону и фактическое пересечение.

API [HybridShapeFactory.add_new_hybrid_split](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_hybrid_split)

```python
add_new_hybrid_split(i_element1: Reference, i_element2: Reference, i_orientation: int) -> HybridShapeSplit
```

CATIA COM: `o Func AddNewHybridSplit(Reference iElement1, Reference iElement2, long iOrientation) As HybridShapeSplit`.


### 125 Trim Surfaces

**CATIA-125 · direct · P2**

Два элемента и их ориентации; проверять обе сохранённые части.

Проверка: Выбор сохраняемых участков влияет на итоговую оболочку.

API [HybridShapeFactory.add_new_hybrid_trim](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_hybrid_trim)

```python
add_new_hybrid_trim(i_element1: Reference, i_orientation1: int, i_element2: Reference, i_orientation2: int) -> HybridShapeTrim
```

CATIA COM: `o Func AddNewHybridTrim(Reference iElement1, long iOrientation1, Reference iElement2, long iOrientation2) As HybridShapeTrim`.


### 126 Intersection

**CATIA-126 · direct · P2**

Две геометрические опоры; результат может быть точкой, кривой, несколькими компонентами или пустым.

Проверка: Касательный контакт может давать нестабильную кривую.

API [HybridShapeFactory.add_new_intersection](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_intersection)

```python
add_new_intersection(i_object1: Reference, i_object2: Reference) -> HybridShapeIntersection
```

CATIA COM: `o Func AddNewIntersection(Reference iObject1, Reference iObject2) As HybridShapeIntersection`.


### 127 Projection

**CATIA-127 · direct · P2**

Настроить normal/along direction в возвращённом объекте; проверить однозначность проекции.

Проверка: Направленная и нормальная проекции могут существенно различаться.

API [HybridShapeFactory.add_new_project](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_project)

```python
add_new_project(i_element: Reference, i_support: Reference) -> HybridShapeProject
```

CATIA COM: `o Func AddNewProject(Reference iElement, Reference iSupport) As HybridShapeProject`.

Класс настройки [HybridShapeProject](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_project.html#pycatia.hybrid_shape_interfaces.hybrid_shape_project.HybridShapeProject); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 128 Extrapolate

**CATIA-128 · direct · P2**

Граница, исходник, длина или ограничитель; continuity и propagation — отдельные настройки.

Проверка: Продолжение не обязательно сохраняет нужную форму вдали от края.

API [HybridShapeFactory.add_new_extrapol_length](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_extrapol_length)

```python
add_new_extrapol_length(i_boundary: Reference, i_to_extrapol: Reference, i_length: float) -> HybridShapeExtrapol
```

CATIA COM: `o Func AddNewExtrapolLength(Reference iBoundary, Reference iToExtrapol, double iLength) As HybridShapeExtrapol`.

API [HybridShapeFactory.add_new_extrapol_until](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_extrapol_until)

```python
add_new_extrapol_until(i_boundary: Reference, i_to_extrapol: Reference, i_until: Reference) -> HybridShapeExtrapol
```

CATIA COM: `o Func AddNewExtrapolUntil(Reference iBoundary, Reference iToExtrapol, Reference iUntil) As HybridShapeExtrapol`.

Класс настройки [HybridShapeExtrapol](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_extrapol.html#pycatia.hybrid_shape_interfaces.hybrid_shape_extrapol.HybridShapeExtrapol); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 129 Healing

**CATIA-129 · workflow · P2**

Допуски и continuity должны быть явными; измерить изменение геометрии, а не только успешность Update.

Проверка: Допуск исправления не должен скрывать значимое отклонение формы.

API [HybridShapeFactory.add_new_healing](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_healing)

```python
add_new_healing(i_body_toheal: Reference) -> HybridShapeHealing
```

CATIA COM: `o Func AddNewHealing(Reference iBodyToheal) As HybridShapeHealing`.

Класс настройки [HybridShapeHealing](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_healing.html#pycatia.hybrid_shape_interfaces.hybrid_shape_healing.HybridShapeHealing); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 130 Curve Smooth

**CATIA-130 · direct · P2**

Настроить допуск сглаживания и разрешённые изменения; сравнить с исходной кривой.

Проверка: Проверь потерю исходного профиля и важных точек.

API [HybridShapeFactory.add_new_curve_smooth](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_curve_smooth)

```python
add_new_curve_smooth(ip_ia_curve: Reference) -> HybridShapeCurveSmooth
```

CATIA COM: `o Func AddNewCurveSmooth(Reference ipIACurve) As HybridShapeCurveSmooth`.

Класс настройки [HybridShapeCurveSmooth](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_curve_smooth.html#pycatia.hybrid_shape_interfaces.hybrid_shape_curve_smooth.HybridShapeCurveSmooth); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 131 Remove Face и Replace Face

**CATIA-131 · direct · P2**

Solid-операции над гранями; distinct contracts для удаления и замены. Не путать с поверхностным Split.

Проверка: После прямого редактирования проверь объём и зависимости.

API [ShapeFactory.add_new_remove_face](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_remove_face)

```python
add_new_remove_face(i_keep_faces: Reference, i_remove_faces: Reference) -> RemoveFace
```

CATIA COM: `o Func AddNewRemoveFace(Reference iKeepFaces, Reference iRemoveFaces) As RemoveFace`.

API [ShapeFactory.add_new_replace_face](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_replace_face)

```python
add_new_replace_face(i_split_plane: Reference, i_remove_face: Reference, i_splitting_side: CatSplitSide) -> ReplaceFace
```

CATIA COM: `o Func AddNewReplaceFace(Reference iSplitPlane, Reference iRemoveFace, CatSplitSide iSplittingSide) As ReplaceFace`.


## Сборка и организация компонентов

### 132 Existing Component

**CATIA-132 · direct · P3**

Пути существующих файлов и метод импорта; проверить наличие и возвращённое число компонентов.

Проверка: Не теряй связь с исходным CATPart.

API [Products.add_components_from_files](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.add_components_from_files)

```python
add_components_from_files(i_files_list: tuple, i_method: str) -> None
```

CATIA COM: `o Sub AddComponentsFromFiles(CATSafeArrayVariant iFilesList, CATBSTR iMethod)`.


### 133 New Part

**CATIA-133 · direct · P3**

Тип Part и part number; получить документ новой детали и зарегистрировать handle.

Проверка: Выбери осмысленное начало координат.

API [Products.add_new_component](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.add_new_component)

```python
add_new_component(i_documen_type: str, i_part_number: str) -> Product
```

CATIA COM: `o Func AddNewComponent(CATBSTR iDocumenType, CATBSTR iPartNumber) As Product`.


### 134 New Product

**CATIA-134 · direct · P3**

Создать вложенный Product с part number.

Проверка: Группируй по конструкции и обслуживанию.

API [Products.add_new_product](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.add_new_product)

```python
add_new_product(i_part_number: str) -> Product
```

CATIA COM: `o Func AddNewProduct(CATBSTR iPartNumber) As Product`.


### 135 Component Instance

**CATIA-135 · direct · P3**

Добавить instance существующего reference product; различать reference и occurrence.

Проверка: Изменение определения может обновить все её экземпляры.

API [Products.add_component](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.add_component)

```python
add_component(i_reference_product: Product) -> Product
```

CATIA COM: `o Func AddComponent(Product iReferenceProduct) As Product`.


### 136 Replace Component

**CATIA-136 · direct · P3**

Заменить один либо все instances согласно флагу; после замены проверить constraints и ссылки.

Проверка: После замены проверь все привязки и зазоры.

API [Products.replace_component](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.replace_component)

```python
replace_component(i_old_component: Product, i_file_path: str, i_multi_instances: bool) -> Product
```

CATIA COM: `o Func ReplaceComponent(Product iOldComponent, CATBSTR iFilePath, boolean iMultiInstances) As Product`.

API [Products.replace_product](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/products.html#pycatia.product_structure_interfaces.products.Products.replace_product)

```python
replace_product(i_old_component: Product, i_new_reference: Product, i_multi_instances: bool) -> Product
```

CATIA COM: `o Func ReplaceProduct(Product iOldComponent, Product iNewReference, boolean iMultiInstances) As Product`.


### 137 Publication

**CATIA-137 · workflow · P3**

Создать publication и связать с Reference; проверить доступность опубликованной геометрии.

Проверка: Публикация помогает управлению связями, но не исключает их поломку.

API [Product.publications](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.publications)

```python
property publications: Publications
```

CATIA COM: `o Property Publications() As Publications`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Publications.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/publications.html#pycatia.product_structure_interfaces.publications.Publications.add)

```python
add(i_public_name: str) -> Publication
```

CATIA COM: `o Func Add(CATBSTR iPublicName) As Publication`.

API [Publications.set_direct](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/publications.html#pycatia.product_structure_interfaces.publications.Publications.set_direct)

```python
set_direct(i_identifier: CATVariant, i_pointed: 'Reference') -> None
```

CATIA COM: `o Sub SetDirect(CATVariant iIdentifier, Reference iPointed)`.


### 138 Design in Context

**CATIA-138 · partial · P3**

Reference и publication — инфраструктура; полный in-context copy и external links требуют отдельного проверенного workflow, не одного вызова.

Проверка: Контролируй направление зависимостей и избегай циклов.

API [Product.create_reference_from_name](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.create_reference_from_name)

```python
create_reference_from_name(i_label: str) -> Reference
```

CATIA COM: `o Func CreateReferenceFromName(CATBSTR iLabel) As Reference`.

API [Part.create_reference_from_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.create_reference_from_object)

```python
create_reference_from_object(i_object: AnyObject)
```

CATIA COM: `o Func CreateReferenceFromObject(AnyObject iObject) As Reference`.

Класс настройки [Publications](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/publications.html#pycatia.product_structure_interfaces.publications.Publications); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 139 Design Mode и Visualization Mode

**CATIA-139 · direct · P3**

CatWorkModeType и доступность исходных CATPart; после перехода проверить, что геометрия реально загружена.

Проверка: Облегчённое представление может не поддерживать нужные операции.

API [Product.apply_work_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.apply_work_mode)

```python
apply_work_mode(new_mode: CatWorkModeType) -> None
```

CATIA COM: `o Sub ApplyWorkMode(CatWorkModeType newMode)`.


### 140 Part Number и Properties

**CATIA-140 · property · P3**

Reference properties и instance properties различать; изменить нужный reference product, а не все occurrences случайно.

Проверка: Имя файла, номер детали и имя экземпляра различаются.

API [Product.part_number](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.part_number)

```python
property part_number: str
```

CATIA COM: `o Property PartNumber() As CATBSTR`.

Свойство имеет setter.

API [Product.revision](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.revision)

```python
property revision: str
```

CATIA COM: `o Property Revision() As CATBSTR`.

Свойство имеет setter.

API [Product.definition](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.definition)

```python
property definition: str
```

CATIA COM: `o Property Definition() As CATBSTR`.

Свойство имеет setter.

API [Product.nomenclature](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.nomenclature)

```python
property nomenclature: str
```

CATIA COM: `o Property Nomenclature() As CATBSTR`.

Свойство имеет setter.

API [Product.user_ref_properties](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.user_ref_properties)

```python
property user_ref_properties: Parameters
```

CATIA COM: `o Property UserRefProperties() As Parameters`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 141 BOM

**CATIA-141 · direct · P3**

Формат и путь; ограничить область сборки, проверить состав и количество экземпляров в файле.

Проверка: Проверь повторяющиеся экземпляры, номера и структуру подсборок.

API [Product.extract_bom](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.extract_bom)

```python
extract_bom(i_file_type: CatFileType, i_file: str) -> None
```

CATIA COM: `o Sub ExtractBOM(CatFileType iFileType, CATBSTR iFile)`.


## Сборочные зависимости и цифровая проверка

### 142 Fix Component

**CATIA-142 · workflow · P3**

Получить CATIAConstraints и Reference нужного occurrence; создать Fix/Reference constraint, проверить DOF.

Проверка: Не фиксируй все детали вместо построения связей.

API [Product.constraints](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.constraints)

```python
constraints() -> Constraints
```

CATIA COM: `o Func Connections(CATBSTR iConnectionsType) As Collection`.

API [Constraints.add_mono_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_mono_elt_cst)

```python
add_mono_elt_cst(i_cst_type: int, i_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddMonoEltCst(CatConstraintType iCstType, Reference iElem) As Constraint`.


### 143 Coincidence

**CATIA-143 · composite · P4**

Coincidence на осях/плоскостях; References должны включать правильный occurrence path.

Проверка: Соосность вала и отверстия оставляет вращение и осевой сдвиг.

API [Product.constraints](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.constraints)

```python
constraints() -> Constraints
```

CATIA COM: `o Func Connections(CATBSTR iConnectionsType) As Collection`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 144 Contact

**CATIA-144 · workflow · P3**

Контакт соответствует допустимому CatConstraintType для пары поверхностей; ориентацию и знак проверить по результату.

Проверка: Ориентация поверхностей влияет на положение.

API [Product.constraints](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.constraints)

```python
constraints() -> Constraints
```

CATIA COM: `o Func Connections(CATBSTR iConnectionsType) As Collection`.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.


### 145 Offset

**CATIA-145 · workflow · P3**

Расстояние между опорами плюс направление; не определять положение случайной координатой Move.

Проверка: Проверь направление и знак расстояния.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Constraint.orientation](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.orientation)

```python
property orientation: int
```

CATIA COM: `o Property Orientation() As CatConstraintOrientation`.

Свойство имеет setter.


### 146 Angle

**CATIA-146 · workflow · P3**

Угол между допустимыми сборочными опорами и orientation.

Проверка: Сочетание с другими связями может быть избыточным.

API [Constraints.add_bi_elt_cst](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.add_bi_elt_cst)

```python
add_bi_elt_cst(i_cst_type: int, i_first_elem: Reference, i_second_elem: Reference) -> Constraint
```

CATIA COM: `o Func AddBiEltCst(CatConstraintType iCstType, Reference iFirstElem, Reference iSecondElem) As Constraint`.

API [Constraint.dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.dimension)

```python
property dimension: Dimension
```

CATIA COM: `o Property Dimension() As Dimension`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 147 Fix Together

**CATIA-147 · partial · P3**

Методы коллекции подтверждены; CAA-пример использует product.FixTogethers, но getter отсутствует в wrapper Product 0.10.1. Получение коллекции проверить в целевой COM type library; не подставлять GetTechnologicalObject без доказательства. Группа фиксирует относительные положения.

Проверка: Группа ещё может двигаться относительно всей сборки.

API [FixTogethers.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/fix_togethers.html#pycatia.mec_mod_interfaces.fix_togethers.FixTogethers.add)

```python
add() -> FixTogether
```

CATIA COM: `o Func Add() As FixTogether`.

API [FixTogether.add_product](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/fix_together.html#pycatia.mec_mod_interfaces.fix_together.FixTogether.add_product)

```python
add_product(i_product: Product) -> None
```

CATIA COM: `o Sub AddProduct(Product iProduct)`.


### 148 Manipulation и Move

**CATIA-148 · direct · P3**

Матрица преобразования по формату COM; свободное Move не заменяет constraints, проверить Update.

Проверка: Положение мышью не заменяет инженерную зависимость.

API [Product.move](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.move)

```python
property move: Move
```

CATIA COM: `o Property Move() As Move`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Move.apply](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/move.html#pycatia.in_interfaces.move.Move.apply)

```python
apply(i_transformation_array: tuple) -> None
```

CATIA COM: `o Sub Apply(iTransformationArray)`.

API [Product.position](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.position)

```python
property position: Position
```

CATIA COM: `o Property Position() As Position`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Position.set_components](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/position.html#pycatia.in_interfaces.position.Position.set_components)

```python
set_components(i_axis_components_array: tuple) -> None
```

CATIA COM: `o Sub SetComponents(CATSafeArrayVariant iAxisComponentsArray)`.


### 149 Clash и Clearance

**CATIA-149 · workflow · P3**

Создать анализ для явных групп, выбрать collision/contact/clearance, запустить Compute и вернуть structured conflicts.

Проверка: Контакт по проекту и нежелательное пересечение различаются.

API [Product.get_technological_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.get_technological_object)

```python
get_technological_object(i_application_type: str)
```

CATIA COM: `o Func GetTechnologicalObject(CATBSTR iApplicationType) As CATBaseDispatch`.

API [Clashes.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/clashes.html#pycatia.space_analyses_interfaces.clashes.Clashes.add)

```python
add() -> Clash
```

CATIA COM: `o Func Add() As Clash`.

API [Clash.compute](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/clash.html#pycatia.space_analyses_interfaces.clash.Clash.compute)

```python
compute() -> None
```

CATIA COM: `o Sub Compute()`.

API [Clash.clearance](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/clash.html#pycatia.space_analyses_interfaces.clash.Clash.clearance)

```python
property clearance: float
```

CATIA COM: `o Property Clearance() As double`.

Свойство имеет setter.

API [Clash.interference_type](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/clash.html#pycatia.space_analyses_interfaces.clash.Clash.interference_type)

```python
property interference_type: CatClashInterferenceType
```

CATIA COM: `o Property InterferenceType() As CatClashInterferenceType`.

Свойство имеет setter.

API [Clash.conflicts](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/clash.html#pycatia.space_analyses_interfaces.clash.Clash.conflicts)

```python
property conflicts: Conflicts
```

CATIA COM: `o Property Conflicts() As Conflicts`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 150 Sectioning

**CATIA-150 · workflow · P3**

Настроить плоскость/режим section и получить доступные результаты; не путать с Drafting Section View.

Проверка: Сечение для осмотра не является вырезом в модели.

API [Product.get_technological_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.get_technological_object)

```python
get_technological_object(i_application_type: str)
```

CATIA COM: `o Func GetTechnologicalObject(CATBSTR iApplicationType) As CATBaseDispatch`.

API [Sections.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/sections.html#pycatia.space_analyses_interfaces.sections.Sections.add)

```python
add() -> Section
```

CATIA COM: `o Func Add() As Section`.

Класс настройки [Section](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/section.html#pycatia.space_analyses_interfaces.section.Section); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 151 DMU Kinematics

**CATIA-151 · workflow · P3**

Отдельный лицензируемый backend; фиксированное звено, joint types, оси и команды; получить реальный status/DOF перед симуляцией.

Проверка: Кинематика не вычисляет автоматически прочность или контактные силы.

API [Product.get_technological_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.get_technological_object)

```python
get_technological_object(i_application_type: str)
```

CATIA COM: `o Func GetTechnologicalObject(CATBSTR iApplicationType) As CATBaseDispatch`.

API [Mechanisms.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanisms.html#pycatia.kinematics_interfaces.mechanisms.Mechanisms.add)

```python
add() -> Mechanism
```

CATIA COM: `o Func Add() As Mechanism`.

API [Mechanism.add_joint](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanism.html#pycatia.kinematics_interfaces.mechanism.Mechanism.add_joint)

```python
add_joint(i_joint_type: str, i_list_elem: tuple) -> Joint
```

CATIA COM: `o Func AddJoint(CATBSTR iJointType, CATSafeArrayVariant iListElem) As Joint`.

API [Mechanism.add_command](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanism.html#pycatia.kinematics_interfaces.mechanism.Mechanism.add_command)

```python
add_command(i_cmd_type: str, i_joint: Joint) -> MechanismCommand
```

CATIA COM: `o Func AddCommand(CATBSTR iCmdType, Joint iJoint) As MechanismCommand`.

API [Mechanism.put_command_values_with_multi_steps](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanism.html#pycatia.kinematics_interfaces.mechanism.Mechanism.put_command_values_with_multi_steps)

```python
put_command_values_with_multi_steps(i_cmd_values: tuple, i_nb_steps: int, o_step_reached: int) -> None
```

CATIA COM: `o Sub PutCommandValuesWithMultiSteps(CATSafeArrayVariant iCmdValues, long iNbSteps, long oStepReached)`.

API [Mechanism.get_product_motion](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanism.html#pycatia.kinematics_interfaces.mechanism.Mechanism.get_product_motion)

```python
get_product_motion(i_product: Product, io_motion: tuple) -> None
```

CATIA COM: `o Sub GetProductMotion(Product iProduct, CATSafeArrayVariant ioMotion)`.

API [Mechanism.nb_dof](https://pycatia.readthedocs.io/en/latest/api/pycatia/kinematics_interfaces/mechanism.html#pycatia.kinematics_interfaces.mechanism.Mechanism.nb_dof)

```python
property nb_dof: int
```

CATIA COM: `o Property NbDof() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


## Drafting и создание видов

### 152 Front View

**CATIA-152 · workflow · P3**

Источник CATPart/CATProduct и два независимых вектора проекции; после Update проверить вид и масштаб.

Проверка: Выбирай вид, лучше всего раскрывающий форму детали.

API [DrawingViews.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_views.html#pycatia.drafting_interfaces.drawing_views.DrawingViews.add)

```python
add(i_drawing_view_name: str) -> DrawingView
```

CATIA COM: `o Func Add(CATBSTR iDrawingViewName) As DrawingView`.

API [DrawingView.generative_behavior](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.generative_behavior)

```python
property generative_behavior: DrawingViewGenerativeBehavior
```

CATIA COM: `o Property GenerativeBehavior() As DrawingViewGenerativeBehavior`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingViewGenerativeBehavior.document](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.document)

```python
property document: AnyObject
```

CATIA COM: `o Property Document() As AnyObject`.

Свойство имеет setter.

API [DrawingViewGenerativeBehavior.define_front_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_front_view)

```python
define_front_view(i_x1: float, i_y1: float, i_z1: float, i_x2: float, i_y2: float, i_z2: float) -> None
```

CATIA COM: `o Sub DefineFrontView(double iX1, double iY1, double iZ1, double iX2, double iY2, double iZ2)`.

API [DrawingViewGenerativeBehavior.update](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.update)

```python
update() -> None
```

CATIA COM: `o Sub Update()`.


### 153 Projection View

**CATIA-153 · direct · P3**

Родительский generative behavior и CatProjViewType; layout первого/третьего угла проекции задаётся отдельно.

Проверка: Проверь принятую систему проекций листа.

API [DrawingViewGenerativeBehavior.define_projection_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_projection_view)

```python
define_projection_view(i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior', i_type: int) -> None
```

CATIA COM: `o Sub DefineProjectionView(DrawingViewGenerativeBehavior iParentViewGenerativeBehavior, CatProjViewType iType)`.


### 154 Isometric View

**CATIA-154 · direct · P3**

Два вектора ориентации; orthogonal orientation не брать из текущей камеры неявно.

Проверка: Не заменяет необходимые виды и разрезы для размеров.

API [DrawingViewGenerativeBehavior.define_isometric_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_isometric_view)

```python
define_isometric_view(i_x1: float, i_y1: float, i_z1: float, i_x2: float, i_y2: float, i_z2: float) -> None
```

CATIA COM: `o Sub DefineIsometricView(double iX1, double iY1, double iZ1, double iX2, double iY2, double iZ2)`.


### 155 Auxiliary View

**CATIA-155 · direct · P3**

Линия проекции, направление, parent view по сигнатуре; проверить правильную сторону.

Проверка: Полезен для истинной формы наклонного элемента.

API [DrawingViewGenerativeBehavior.define_auxiliary_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_auxiliary_view)

```python
define_auxiliary_view(i_x_start_point: float, i_y_start_point: float, i_x_end_point: float, y_end_point: float, i_side_to_draw: int, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineAuxiliaryView(double iXStartPoint, double iYStartPoint, double iXEndPoint, double YEndPoint, short iSideToDraw, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 156 Section View

**CATIA-156 · direct · P3**

Профиль сечения в координатах вида, SectionView, тип профиля, сторона и parent view.

Проверка: Проверь направление взгляда и линию сечения.

API [DrawingViewGenerativeBehavior.define_section_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_section_view)

```python
define_section_view(i_profile: tuple, i_section_type: str, i_profile_type: str, i_side_to_draw: int, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineSectionView(CATSafeArrayVariant iProfile, CATBSTR iSectionType, CATBSTR iProfileType, short iSideToDraw, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 157 Section Cut

**CATIA-157 · direct · P3**

Тот же метод с режимом SectionCut; вид и сечение не разные constructors.

Проверка: Отличается от полного Section View.

API [DrawingViewGenerativeBehavior.define_section_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_section_view)

```python
define_section_view(i_profile: tuple, i_section_type: str, i_profile_type: str, i_side_to_draw: int, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineSectionView(CATSafeArrayVariant iProfile, CATBSTR iSectionType, CATBSTR iProfileType, short iSideToDraw, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 158 Offset и Aligned Section

**CATIA-158 · direct · P3**

Профиль нескольких сегментов и режим Offset/Aligned в точном строковом формате API; проверить повороты сечения.

Проверка: Выбор вида разреза должен соответствовать требуемому представлению.

API [DrawingViewGenerativeBehavior.define_section_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_section_view)

```python
define_section_view(i_profile: tuple, i_section_type: str, i_profile_type: str, i_side_to_draw: int, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineSectionView(CATSafeArrayVariant iProfile, CATBSTR iSectionType, CATBSTR iProfileType, short iSideToDraw, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 159 Detail View

**CATIA-159 · direct · P3**

Контур/окружность, parent behavior и ориентация; масштаб задаётся на DrawingView.

Проверка: Ясно укажи границу и масштаб увеличения.

API [DrawingViewGenerativeBehavior.define_circular_detail_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_circular_detail_view)

```python
define_circular_detail_view(i_x_center: float, i_y_center: float, i_radius: float, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineCircularDetailView(double iXCenter, double iYCenter, double iRadius, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.

API [DrawingViewGenerativeBehavior.define_polygonal_detail_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_polygonal_detail_view)

```python
define_polygonal_detail_view(i_profile: tuple, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefinePolygonalDetailView(CATSafeArrayVariant iProfile, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 160 Clipping View

**CATIA-160 · direct · P3**

Обрезка выбранного вида по контуру; проверить сохранённую область.

Проверка: Обрезка не должна скрывать необходимые сведения.

API [DrawingViewGenerativeBehavior.define_circular_clipping_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_circular_clipping_view)

```python
define_circular_clipping_view(x_center: float, y_center: float, radius: float) -> None
```

CATIA COM: `o Sub DefineCircularClippingView(double XCenter, double YCenter, double Radius)`.

API [DrawingViewGenerativeBehavior.define_polygonal_clipping_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_polygonal_clipping_view)

```python
define_polygonal_clipping_view(profile: tuple) -> None
```

CATIA COM: `o Sub DefinePolygonalClippingView(CATSafeArrayVariant profil)`.


### 161 Broken View

**CATIA-161 · direct · P3**

Два профиля и направление разрыва; реальные размеры не изменяются.

Проверка: Размеры должны отражать полную геометрию.

API [DrawingViewGenerativeBehavior.define_broken_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_broken_view)

```python
define_broken_view(i_broken_lines_extremities: tuple, i_x_direction: float, i_y_direction: float) -> None
```

CATIA COM: `o Sub DefineBrokenView(CATSafeArrayVariant iBrokenLinesExtremities, double iXDirection, double iYDirection)`.


### 162 Breakout View

**CATIA-162 · direct · P3**

Замкнутый 2D профиль и глубина; ограничить действие нужным видом.

Проверка: Проверь, что вскрыт именно нужный элемент.

API [DrawingViewGenerativeBehavior.define_breakout](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_breakout)

```python
define_breakout(i_profil: tuple, i_plane1: tuple, i_plane2: tuple) -> None
```

CATIA COM: `o Sub DefineBreakout(CATSafeArrayVariant iProfil, CATSafeArrayVariant iPlane1, CATSafeArrayVariant iPlane2)`.


### 163 Unfolded View

**CATIA-163 · direct · P3**

Доступная развёртка и ориентация; этот API не создаёт корректную sheet-metal модель из произвольного solid.

Проверка: Линии гиба и контур заготовки должны быть различимы.

API [DrawingViewGenerativeBehavior.define_unfolded_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_unfolded_view)

```python
define_unfolded_view(i_x1: float, i_y1: float, i_z1: float, i_x2: float, i_y2: float, i_z2: float) -> None
```

CATIA COM: `o Sub DefineUnfoldedView(double iX1, double iY1, double iZ1, double iX2, double iY2, double iZ2)`.


## Drafting и размеры обозначения оформление

### 164 Length и Distance Dimensions

**CATIA-164 · workflow · P3**

Тип размера, tuple геометрических объектов, pick coordinates и направление; проверить привязку к правильным элементам.

Проверка: Не дублируй один управляющий размер на нескольких видах.

API [DrawingDimensions.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add)

```python
add(i_type_dim: int, i_geom_elem: tuple[AnyObject], i_pt_coord_elem: tuple, i_line_rep: int) -> DrawingDimension
```

CATIA COM: `o Func Add(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CatDimLineRep iLineRep) As DrawingDimension`.

API [DrawingDimensions.add2](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add2)

```python
add2(i_type_dim: int, i_geom_elem: tuple, i_pt_coord_elem: tuple, i_ldc_ref_elem: Union[AnyObject, VBANothing], i_ldc_ref_angle: int) -> DrawingDimension
```

CATIA COM: `o Func Add2(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CATVariant iLDCRefElem, long iLDCRefAngle) As DrawingDimension`.


### 165 Radius Diameter Angle

**CATIA-165 · workflow · P3**

CatDimType для radius/diameter/angle и соответствующий набор геометрии.

Проверка: Выбирай представление, однозначно показывающее измеряемую геометрию.

API [DrawingDimensions.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add)

```python
add(i_type_dim: int, i_geom_elem: tuple[AnyObject], i_pt_coord_elem: tuple, i_line_rep: int) -> DrawingDimension
```

CATIA COM: `o Func Add(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CatDimLineRep iLineRep) As DrawingDimension`.

API [DrawingDimensions.add2](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add2)

```python
add2(i_type_dim: int, i_geom_elem: tuple, i_pt_coord_elem: tuple, i_ldc_ref_elem: Union[AnyObject, VBANothing], i_ldc_ref_angle: int) -> DrawingDimension
```

CATIA COM: `o Func Add2(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CATVariant iLDCRefElem, long iLDCRefAngle) As DrawingDimension`.


### 166 Chained Dimensions

**CATIA-166 · composite · P4**

Создать связанный набор размеров соседних пар и разместить подписи; готовый универсальный constructor цепочки здесь не подтверждён.

Проверка: Учитывай накопление допусков в цепи.

API [DrawingDimensions.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add)

```python
add(i_type_dim: int, i_geom_elem: tuple[AnyObject], i_pt_coord_elem: tuple, i_line_rep: int) -> DrawingDimension
```

CATIA COM: `o Func Add(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CatDimLineRep iLineRep) As DrawingDimension`.

API [DrawingDimension.move_value](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.move_value)

```python
move_value(x: float, y: float, sub_part: int, dim_angle_behavior: int) -> None
```

CATIA COM: `o Sub MoveValue(double X, double Y, long SubPart, long DimAngleBehavior)`.


### 167 Cumulated и Baseline Dimensions

**CATIA-167 · partial · P3**

Baseline реализовать повторными размерами от общей базы; cumulate/coordinate behavior проверять отдельно, не обещать UI-equivalence.

Проверка: База должна иметь функциональный смысл.

API [DrawingDimensions.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimensions.html#pycatia.drafting_interfaces.drawing_dimensions.DrawingDimensions.add)

```python
add(i_type_dim: int, i_geom_elem: tuple[AnyObject], i_pt_coord_elem: tuple, i_line_rep: int) -> DrawingDimension
```

CATIA COM: `o Func Add(CatDimType iTypeDim, CATSafeArrayVariant iGeomElem, CATSafeArrayVariant iPtCoordElem, CatDimLineRep iLineRep) As DrawingDimension`.

API [DrawingDimension.cumulate_mode](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.cumulate_mode)

```python
property cumulate_mode: bool
```

CATIA COM: `o Property CumulateMode() As boolean`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingView.coord_dims](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.coord_dims)

```python
property coord_dims: DrawingCoordDims
```

CATIA COM: `Property CoordDims() As DrawingCoordDims`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 168 Center Line и Center Mark

**CATIA-168 · partial · P3**

Возможно рисование 2D осевой графики, но полноценные associative Center Line/Center Mark напрямую не подтверждены; отдельно проверить стандарты и формат линии.

Проверка: Не заменяют размер положения отверстия.

API [DrawingView.factory_2d](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.factory_2d)

```python
property factory_2d: Factory2D
```

CATIA COM: `o Property Factory2D() As Factory2D`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Factory2D.create_line](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/factory_2D.html#pycatia.sketcher_interfaces.factory_2D.Factory2D.create_line)

```python
create_line(i_x1: float, i_y1: float, i_x2: float, i_y2: float) -> Line2D
```

CATIA COM: `o Func CreateLine(double iX1, double iY1, double iX2, double iY2) As Line2D`.

API [Geometry2D.construction](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/geometry_2D.html#pycatia.sketcher_interfaces.geometry_2D.Geometry2D.construction)

```python
property construction: bool
```

CATIA COM: `o Property Construction() As boolean`.

Свойство имеет setter.


### 169 Text with Leader

**CATIA-169 · workflow · P3**

Текст, положение и конец выноски; associative_element задавать осмысленно, проверить перестроение вида.

Проверка: Текст не должен противоречить геометрии и размерам.

API [DrawingTexts.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_texts.html#pycatia.drafting_interfaces.drawing_texts.DrawingTexts.add)

```python
add(i_drawing_text: str, i_position_x: float, i_position_y: float) -> DrawingText
```

CATIA COM: `o Func Add(CATBSTR iDrawingText, double iPositionX, double iPositionY) As DrawingText`.

API [DrawingText.leaders](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_text.html#pycatia.drafting_interfaces.drawing_text.DrawingText.leaders)

```python
property leaders
```

CATIA COM: `o Property Leaders() As DrawingLeaders`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingLeaders.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_leaders.html#pycatia.drafting_interfaces.drawing_leaders.DrawingLeaders.add)

```python
add(i_head_point_x: float, i_head_point_y: float) -> DrawingLeader
```

CATIA COM: `o Func Add(double iHeadPointX, double iHeadPointY) As DrawingLeader`.


### 170 Hatching и Area Fill

**CATIA-170 · partial · P3**

Штриховка generated section следует настройкам чертежа/материала. Прямой произвольный Area Fill API в просмотренном Drafting не подтверждён.

Проверка: Избегай штриховки пустот и нечитаемой плотности.

API [DrawingViewGenerativeBehavior.define_section_view](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.define_section_view)

```python
define_section_view(i_profile: tuple, i_section_type: str, i_profile_type: str, i_side_to_draw: int, i_parent_view_generative_behavior: 'DrawingViewGenerativeBehavior') -> None
```

CATIA COM: `o Sub DefineSectionView(CATSafeArrayVariant iProfile, CATBSTR iSectionType, CATBSTR iProfileType, short iSideToDraw, DrawingViewGenerativeBehavior iParentViewGenerativeBehavior)`.


### 171 Dimension Tolerances

**CATIA-171 · direct · P3**

Задать тип, текстовые/численные границы и display mode; перечитать реальное значение, не подменять dimension text.

Проверка: Точность выбирают по функции и изготовлению.

API [DrawingDimension.set_tolerances](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.set_tolerances)

```python
set_tolerances(i_tol_type: int, itol_name: str, i_up_tol: str, i_low_tol: str, id_up_tol: float, id_low_tol: float, display_mode: int) -> None
```

CATIA COM: `o Sub SetTolerances(long iTolType, CATBSTR itolName, CATBSTR iUpTol, CATBSTR iLowTol, double idUpTol, double idLowTol, long DisplayMode)`.

API [DrawingDimension.get_tolerances](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.get_tolerances)

```python
get_tolerances() -> tuple[int, str, str, str, float, float, int]
```

CATIA COM: `o Sub GetTolerances(long oTolType, CATBSTR oTolName, CATBSTR oUpTol, CATBSTR oLowTol, double odUpTol, double odLowTol, long oDisplayMode)`.


### 172 Datum и Geometrical Tolerance

**CATIA-172 · workflow · P3**

Создать геометрическую рамку доступными методами; datum association и семантику GD&T проверять отдельно. FTA 3D — другой интерфейс.

Проверка: GD&T требует отдельного изучения применяемого стандарта.

API [DrawingView.gdts](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.gdts)

```python
property gdts: DrawingGDTs
```

CATIA COM: `Property GDTs() As DrawingGDTs`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingGDTs.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_gdts.html#pycatia.drafting_interfaces.drawing_gdts.DrawingGDTs.add)

```python
add(i_position_leader_x: float, i_position_leader_y: float, i_position_x: float, i_position_y: float, i_gdt_symbol: int, i_text: str) -> DrawingGDT
```

CATIA COM: `Func Add(double iPositionLeaderX,double iPositionLeaderY,double iPositionX,double iPositionY,long iGDTSymbol,CATBSTR iText) As DrawingGDT`.

API [DrawingGDT.get_text_range](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_gdt.html#pycatia.drafting_interfaces.drawing_gdt.DrawingGDT.get_text_range)

```python
get_text_range(i_row_number: int, i_number: int) -> DrawingTextRange
```

CATIA COM: `Func GetTextRange(long iRowNumber,long iNumber) As DrawingTextRange`.

API [DrawingTextRange.text](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_text_range.html#pycatia.drafting_interfaces.drawing_text_range.DrawingTextRange.text)

```python
property text: str
```

CATIA COM: `o Property Text() As CATBSTR`.

Свойство имеет setter.


### 173 Surface Finish Symbol

**CATIA-173 · unconfirmed · P4**

Прямой Drafting Surface Finish Symbol API не найден в просмотренном наборе. 3D FTA Roughness не эквивалентен 2D символу; не выдавать текстовый суррогат за semantic annotation.

Проверка: Шероховатость не является декоративным символом.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 174 Sheet Scale и View Scale

**CATIA-174 · property · P3**

Масштаб листа и вида менять отдельно; не масштабировать фактические размеры детали.

Проверка: Изменение масштаба не меняет действительных размеров детали.

API [DrawingSheet.scale](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_sheet.html#pycatia.drafting_interfaces.drawing_sheet.DrawingSheet.scale)

```python
property scale: float
```

CATIA COM: `o Property Scale() As double`.

Свойство имеет setter.

API [DrawingView.scale](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.scale)

```python
property scale: float
```

CATIA COM: `o Property Scale() As double`.

Свойство имеет setter.


### 175 Sheet Background и Title Block

**CATIA-175 · workflow · P3**

Выбрать background view по проверенному типу/контексту; рамка линиями и штамп текстами, явно заданный формат листа.

Проверка: Заполни номер, ревизию, единицы и материал по заданию.

API [DrawingSheet.views](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_sheet.html#pycatia.drafting_interfaces.drawing_sheet.DrawingSheet.views)

```python
property views: DrawingViews
```

CATIA COM: `o Property Views() As DrawingViews`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingViews.item](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_views.html#pycatia.drafting_interfaces.drawing_views.DrawingViews.item)

```python
item(i_index: CATVariant) -> DrawingView
```

CATIA COM: `o Func Item(CATVariant iIndex) As DrawingView`.

API [DrawingView.factory_2d](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.factory_2d)

```python
property factory_2d: Factory2D
```

CATIA COM: `o Property Factory2D() As Factory2D`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingView.texts](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view.html#pycatia.drafting_interfaces.drawing_view.DrawingView.texts)

```python
property texts: DrawingTexts
```

CATIA COM: `o Property Texts() As DrawingTexts`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


## Листовой металл и развёртки

### 176 Sheet Metal Parameters

**CATIA-176 · unconfirmed · P4**

Параметры доступны как generic Parameters, но dedicated Sheet Metal Parameters factory в этом API-наборе не найден. Требуется проверенный template либо другой лицензированный Automation API.

Проверка: Параметры должны соответствовать материалу и процессу.

Класс настройки [Parameters](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 177 Wall

**CATIA-177 · unconfirmed · P4**

Wall constructor листового металла не подтверждён; Pad не является эквивалентом.

Проверка: Первая стенка определяет важную опору развёртки.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 178 Wall on Edge

**CATIA-178 · unconfirmed · P4**

Wall on Edge constructor не подтверждён; шаблон PowerCopy допустим только после отдельной проверки входов и развёртки.

Проверка: Проверь способ измерения высоты стенки.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 179 Bend

**CATIA-179 · unconfirmed · P4**

Sheetmetal Bend constructor не подтверждён; поверхности и fillet не заменяют sheetmetal semantics.

Проверка: Контролируй внутренний радиус и обработку концов гиба.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 180 Bend from Flat

**CATIA-180 · unconfirmed · P4**

Bend from Flat constructor не подтверждён; исследовать template/recorded macro в конкретной CATIA.

Проверка: Проверь неподвижную сторону и положение линии.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 181 Flange

**CATIA-181 · unconfirmed · P4**

Sheetmetal Flange constructor не подтверждён в просмотренном pycatia API.

Проверка: Учитывай доступность инструмента и возможное пересечение.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 182 Hem

**CATIA-182 · unconfirmed · P4**

Sheetmetal Hem constructor не подтверждён в просмотренном pycatia API.

Проверка: Реальный подгиб требует технологического зазора.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 183 Cutout и Hole

**CATIA-183 · partial · P3**

Обычные hole/pocket доступны, но sheetmetal Cutout с правилами направления и unfold требует отдельной реализации и теста.

Проверка: Проверь расстояния до гибов по производственным требованиям.

API [ShapeFactory.add_new_hole_from_sketch](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_hole_from_sketch)

```python
add_new_hole_from_sketch(i_sketch: Sketch, i_depth: float) -> Hole
```

CATIA COM: `o Func AddNewHoleFromSketch(Sketch iSketch, double iDepth) As Hole`.

API [ShapeFactory.add_new_pocket](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shape_factory.html#pycatia.part_interfaces.shape_factory.ShapeFactory.add_new_pocket)

```python
add_new_pocket(i_sketch: Sketch, i_height: float) -> Pocket
```

CATIA COM: `o Func AddNewPocket(Sketch iSketch, double iHeight) As Pocket`.


### 184 Corner Relief

**CATIA-184 · unconfirmed · P4**

Corner Relief constructor не подтверждён. Не автоматически заменять generic Pocket без проверки развертки.

Проверка: Форма должна предотвращать нежелательное наложение материала.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 185 Fold и Unfold

**CATIA-185 · unconfirmed · P4**

Sheetmetal Fold/Unfold не подтверждён. HybridShapeFactory.add_new_unfold относится к GSD и не доказывает эквивалентность этой команде.

Проверка: Контролируй выбранную неподвижную грань.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


### 186 Bend Allowance и K Factor

**CATIA-186 · partial · P3**

Можно менять заранее найденные параметры шаблона; расположение K Factor/Bend Allowance и их смысл зависят от конкретной модели/процесса.

Проверка: K не является универсальной константой для всех процессов.

API [Parameters.item](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.item)

```python
item(index: CATVariant) -> AnyParameter
```

CATIA COM: `o Func Item( CATVariant iIndex) As Parameter`.

API [Parameter.valuate_from_string](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameter.html#pycatia.knowledge_interfaces.parameter.Parameter.valuate_from_string)

```python
valuate_from_string(i_value: str) -> None
```

CATIA COM: `o Sub ValuateFromString(CATBSTR iValue)`.


### 187 Bead и Stamp

**CATIA-187 · unconfirmed · P4**

Sheetmetal Bead/Stamp constructors не подтверждены; не придумывать add_new_bead/add_new_stamp.

Проверка: Геометрия не заменяет проверку возможности формования.

Прямой вызов не подтверждён. Возвращать unsupported до отдельного исследования.


## Параметры семейства деталей и автоматизация

### 188 Parameters

**CATIA-188 · direct · P3**

Типизированные параметры; для dimension задать величину и единицы, читать назад после записи.

Проверка: Физические величины должны иметь корректные единицы.

API [Parameters.create_dimension](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.create_dimension)

```python
create_dimension(i_name: str, i_magnitude: str, i_value: float) -> Dimension
```

CATIA COM: `o Func CreateDimension(CATBSTR iName, CATBSTR iMagnitude, double iValue) As Dimension`.

API [Parameters.create_real](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.create_real)

```python
create_real(i_name: str, i_value: float) -> RealParam
```

CATIA COM: `o Func CreateReal(CATBSTR iName, double iValue) As RealParam`.

API [Parameters.create_integer](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.create_integer)

```python
create_integer(i_name: str, i_value: int) -> IntParam
```

CATIA COM: `o Func CreateInteger(CATBSTR iName, long iValue) As IntParam`.

API [Parameters.create_boolean](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.create_boolean)

```python
create_boolean(i_name: str, i_value: bool) -> BoolParam
```

CATIA COM: `o Func CreateBoolean(CATBSTR iName, boolean iValue) As BoolParam`.

API [Parameters.create_string](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.create_string)

```python
create_string(i_name: str, i_value: str) -> StrParam
```

CATIA COM: `o Func CreateString(CATBSTR iName, CATBSTR iValue) As StrParam`.

API [Parameter.valuate_from_string](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameter.html#pycatia.knowledge_interfaces.parameter.Parameter.valuate_from_string)

```python
valuate_from_string(i_value: str) -> None
```

CATIA COM: `o Sub ValuateFromString(CATBSTR iValue)`.


### 189 Formula

**CATIA-189 · direct · P3**

Имя, комментарий, output parameter и выражение CATIA; имена References получать через API, не собирать строкой наугад.

Проверка: Избегай циклических зависимостей.

API [Relations.create_formula](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_formula)

```python
create_formula(i_name: str, i_comment: str, i_output_parameter: Parameter, i_formula_body: str)
```

CATIA COM: `o Func CreateFormula(CATBSTR iName, CATBSTR iComment, Parameter iOutputParameter, CATBSTR iFormulaBody) As Formula`.

API [Formula.modify](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relation.html#pycatia.knowledge_interfaces.relation.Relation.modify)

```python
modify(i_value: str) -> None
```

Объявлен в `Relation.modify` и наследуется целевым классом.

CATIA COM: `o Sub Modify(CATBSTR iValue)`.

API [Parameters.get_name_to_use_in_relation](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/parameters.html#pycatia.knowledge_interfaces.parameters.Parameters.get_name_to_use_in_relation)

```python
get_name_to_use_in_relation(i_object: AnyObject) -> str
```

CATIA COM: `o Func GetNameToUseInRelation(AnyObject iObject) As CATBSTR`.


### 190 Design Table

**CATIA-190 · workflow · P3**

Файл таблицы, связи столбцов с параметрами и выбранная конфигурация; проверить все изменённые значения.

Проверка: Каждая строка должна проходить геометрическую проверку.

API [Relations.create_design_table](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_design_table)

```python
create_design_table(i_name: str, i_comment: str, i_copy_mode: bool, i_sheet_path: Path) -> DesignTable
```

CATIA COM: `o Func CreateDesignTable(CATBSTR iName, CATBSTR iComment, boolean iCopyMode, CATBSTR iSheetPath) As DesignTable`.

API [DesignTable.add_association](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/design_table.html#pycatia.knowledge_interfaces.design_table.DesignTable.add_association)

```python
add_association(i_parameter: 'Parameter', i_sheet_column: str) -> None
```

CATIA COM: `o Sub AddAssociation(Parameter iParameter, CATBSTR iSheetColumn)`.

API [DesignTable.configuration](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/design_table.html#pycatia.knowledge_interfaces.design_table.DesignTable.configuration)

```python
property configuration: int
```

CATIA COM: `o Property Configuration() As short`.

Свойство имеет setter.

API [DesignTable.synchronize](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/design_table.html#pycatia.knowledge_interfaces.design_table.DesignTable.synchronize)

```python
synchronize() -> None
```

CATIA COM: `o Sub Synchronize()`.


### 191 Rule

**CATIA-191 · direct · P3**

Для Rule использовать create_program(name, comment, program_body), возвращающий Rule. Метод create_rule в Relations отсутствует; проверить синтаксис Knowledgeware и доступность лицензии.

Проверка: Проверь поведение на границах условий.

API [Relations.create_program](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_program)

```python
create_program(i_name: str, i_comment: str, i_program_body: str) -> Rule
```

CATIA COM: `o Func CreateProgram(CATBSTR iName, CATBSTR iComment, CATBSTR iProgramBody) As Rule`.

Класс настройки [Rule](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/rule.html#pycatia.knowledge_interfaces.rule.Rule); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 192 Check

**CATIA-192 · direct · P3**

Условие и параметры; результат check не считать автоматическим исправлением модели.

Проверка: Проверка обнаруживает нарушение, но не обязана его исправлять.

API [Relations.create_check](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/relations.html#pycatia.knowledge_interfaces.relations.Relations.create_check)

```python
create_check(i_name: str, i_comment: str, i_check_body: str) -> Check
```

CATIA COM: `o Func CreateCheck(CATBSTR iName, CATBSTR iComment, CATBSTR iCheckBody) As Check`.

Класс настройки [Check](https://pycatia.readthedocs.io/en/latest/api/pycatia/knowledge_interfaces/check.html#pycatia.knowledge_interfaces.check.Check); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 193 PowerCopy

**CATIA-193 · workflow · P3**

PowerCopy из утверждённого template: задать все named inputs и параметры, завершить обе фазы и проверить созданные features.

Проверка: Нужен ясный контракт входов и параметров.

API [Part.get_customer_factory](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.get_customer_factory)

```python
get_customer_factory(i_factory_iid: str) -> Factory
```

CATIA COM: `o Func GetCustomerFactory(CATBSTR iFactoryIID) As Factory`.

API [InstanceFactory.begin_instance_factory](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.begin_instance_factory)

```python
begin_instance_factory(i_name_of_reference: str, i_name_of_document: str) -> None
```

CATIA COM: `o Sub BeginInstanceFactory(CATBSTR iNameOfReference, CATBSTR iNameOfDocument)`.

API [InstanceFactory.begin_instantiate](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.begin_instantiate)

```python
begin_instantiate() -> None
```

CATIA COM: `o Sub BeginInstantiate()`.

API [InstanceFactory.put_input_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.put_input_data)

```python
put_input_data(i_name: str, i_input: AnyObject) -> None
```

CATIA COM: `o Sub PutInputData(CATBSTR iName, CATBaseDispatch iInput)`.

API [InstanceFactory.get_parameter](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.get_parameter)

```python
get_parameter(i_name: str) -> AnyObject
```

CATIA COM: `o Func GetParameter(CATBSTR iName) As AnyObject`.

API [InstanceFactory.instantiate](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.instantiate)

```python
instantiate() -> AnyObject
```

CATIA COM: `o Func Instantiate() As AnyObject`.

API [InstanceFactory.end_instantiate](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.end_instantiate)

```python
end_instantiate() -> None
```

CATIA COM: `o Sub EndInstantiate()`.

API [InstanceFactory.end_instance_factory](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.end_instance_factory)

```python
end_instance_factory() -> None
```

CATIA COM: `o Sub EndInstanceFactory()`.


### 194 User Feature

**CATIA-194 · workflow · P3**

User Feature instance из разрешённого reference; отличать instantiation от создания определения User Feature.

Проверка: Доступность и создание зависят от конфигурации.

API [InstanceFactory.add_instance](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory.add_instance)

```python
add_instance(i_reference: AnyObject) -> AnyObject
```

CATIA COM: `o Func AddInstance(AnyObject iReference) As AnyObject`.

Класс настройки [InstanceFactory](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/instance_factory.html#pycatia.mec_mod_interfaces.instance_factory.InstanceFactory); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 195 Publication

**CATIA-195 · workflow · P3**

Тот же API, что в пункте 137; один общий backend, без дублирования tools.

Проверка: Не публикуй случайные рёбра без необходимости.

API [Publications.add](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/publications.html#pycatia.product_structure_interfaces.publications.Publications.add)

```python
add(i_public_name: str) -> Publication
```

CATIA COM: `o Func Add(CATBSTR iPublicName) As Publication`.

API [Publications.set_direct](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/publications.html#pycatia.product_structure_interfaces.publications.Publications.set_direct)

```python
set_direct(i_identifier: CATVariant, i_pointed: 'Reference') -> None
```

CATIA COM: `o Sub SetDirect(CATVariant iIdentifier, Reference iPointed)`.


### 196 Macro и CATScript

**CATIA-196 · direct · P3**

Произвольный запуск скриптов не публиковать LLM как универсальную замену всех tools. Разрешать только проверенные макросы с фиксированным контрактом.

Проверка: Запись действий не покрывает автоматически весь интерфейс.

API [SystemService.execute_script](https://pycatia.readthedocs.io/en/latest/api/pycatia/system_interfaces/system_service.html#pycatia.system_interfaces.system_service.SystemService.execute_script)

```python
execute_script(i_library_name: str, i_type: CatScriptLibraryType, i_program_name: str, i_function_name: str, i_parameters: list)
```

CATIA COM: `o Func ExecuteScript(CATBSTR iLibraryName, CatScriptLibraryType iType, CATBSTR iProgramName, CATBSTR iFunctionName, CATSafeArrayVariant iParameters) As CATVariant`.

API [Application.system_service](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/application.html#pycatia.in_interfaces.application.Application.system_service)

```python
property system_service: SystemService
```

CATIA COM: `o Property SystemService() As SystemService`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 197 pycatia

**CATIA-197 · infrastructure · P3**

pycatia — Python wrapper, не самостоятельная операция геометрии. Выбрать один backend и не смешивать wrappers с raw COM без явного adapter.

Проверка: Нужна совместимая Windows-среда с CATIA; macOS сам по себе не заменяет её.

Класс настройки [Application](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/application.html#pycatia.in_interfaces.application.Application); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

Класс настройки [Documents](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/documents.html#pycatia.in_interfaces.documents.Documents); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


## Измерения обмен файлами и выпуск модели

### 198 Measure Item

**CATIA-198 · workflow · P1**

Reference и требуемые свойства: length/radius/area/volume/points. Допустимость свойства зависит от geometry_name.

Проверка: Убедись, что выбран нужный геометрический объект.

API [SPAWorkbench.get_measurable](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/spa_workbench.html#pycatia.space_analyses_interfaces.spa_workbench.SPAWorkbench.get_measurable)

```python
get_measurable(i_measured_item: Reference) -> Measurable
```

CATIA COM: `o Func GetMeasurable(Reference iMeasuredItem) As Measurable`.

Класс настройки [Measurable](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 199 Measure Between

**CATIA-199 · workflow · P1**

Два References, поддерживаемые типы. Для occurrences сборки использовать in-context API, где он доступен.

Проверка: Минимальное расстояние не всегда равно расстоянию вдоль заданной оси.

API [Measurable.get_minimum_distance](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable.get_minimum_distance)

```python
get_minimum_distance(i_measured_item)
```

CATIA COM: `Func GetMinimumDistance( Reference iMeasuredItem) As double`.

API [Measurable.get_angle_between](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable.get_angle_between)

```python
get_angle_between(i_measured_item: Reference) -> float
```

CATIA COM member: `GetAngleBetween`; сигнатуру raw COM проверить по wrapper/type library.

API [Measurable.get_minimum_distance_points](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable.get_minimum_distance_points)

```python
get_minimum_distance_points(i_measured_item)
```

CATIA COM: `Sub GetMinimumDistancePoints( Reference iMeasuredItem, CATSafeArrayVariant oCoordinates)`.


### 200 Measure Inertia

**CATIA-200 · workflow · P1**

Инерция нужного Product/Part; вернуть units и выбранную плотность, объяснить sentinel values density.

Проверка: Проверь плотность, единицы и включённые тела.

API [Product.get_technological_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.get_technological_object)

```python
get_technological_object(i_application_type: str)
```

CATIA COM: `o Func GetTechnologicalObject(CATBSTR iApplicationType) As CATBaseDispatch`.

API [Inertia.mass](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.mass)

```python
property mass: float
```

CATIA COM: `o Property Mass() As double`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Inertia.get_cog_position](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.get_cog_position)

```python
get_cog_position() -> tuple
```

CATIA COM: `o Sub GetCOGPosition(CATSafeArrayVariant oCoordinates)`.

API [Inertia.get_inertia_matrix](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.get_inertia_matrix)

```python
get_inertia_matrix() -> tuple
```

CATIA COM: `o Sub GetInertiaMatrix(CATSafeArrayVariant oMatrix)`.

API [Inertia.density](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.density)

```python
property density: float
```

CATIA COM: `o Property Density() As double`.

Свойство имеет setter.


### 201 Apply Material

**CATIA-201 · workflow · P3**

Получить manager через get_item с идентификатором CATMatManager на подходящем объекте Part/Product, обернуть MaterialManager при pycatia backend; загрузить Material из каталога, выбрать цель и link mode.

Проверка: Цвет материала не доказывает корректную плотность или упругость.

API [MaterialManager.apply_material_on_body](https://pycatia.readthedocs.io/en/latest/api/pycatia/cat_mat_interfaces/material_manager.html#pycatia.cat_mat_interfaces.material_manager.MaterialManager.apply_material_on_body)

```python
apply_material_on_body(i_body: Body, i_material: Union[Material, None], i_link_mode: int=0) -> None
```

CATIA COM: `o Sub ApplyMaterialOnBody(Body iBody, Material iMaterial, short iLinkMode)`.

API [MaterialManager.apply_material_on_part](https://pycatia.readthedocs.io/en/latest/api/pycatia/cat_mat_interfaces/material_manager.html#pycatia.cat_mat_interfaces.material_manager.MaterialManager.apply_material_on_part)

```python
apply_material_on_part(i_part: Part, i_material: Union[Material, None], i_link_mode: int=0) -> None
```

CATIA COM: `o Sub ApplyMaterialOnPart(Part iPart, Material iMaterial, short iLinkMode)`.

API [MaterialManager.apply_material_on_product](https://pycatia.readthedocs.io/en/latest/api/pycatia/cat_mat_interfaces/material_manager.html#pycatia.cat_mat_interfaces.material_manager.MaterialManager.apply_material_on_product)

```python
apply_material_on_product(i_product: Product, i_material: Union[Material, None], i_link_mode: int=0) -> None
```

CATIA COM: `o Sub ApplyMaterialOnProduct(Product iProduct, Material iMaterial, short iLinkMode)`.

API [AnyObject.get_item](https://pycatia.readthedocs.io/en/latest/api/pycatia/system_interfaces/any_object.html#pycatia.system_interfaces.any_object.AnyObject.get_item)

```python
get_item(id_name: str) -> 'AnyObject'
```

CATIA COM: `o Func GetItem(CATBSTR IDName) As CATBaseDispatch`.


### 202 STEP Export

**CATIA-202 · direct · P3**

Путь и format string stp по целевому выпуску; проверить файл и обратный импорт геометрии.

Проверка: Исходное дерево параметрических операций обычно не сохраняется.

API [Document.export_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.export_data)

```python
export_data(file_name: Path, file_type: str, overwrite=False) -> None
```

CATIA COM: `Sub ExportData( CATBSTR fileName, CATBSTR format)`.


### 203 IGES Export

**CATIA-203 · direct · P3**

Путь и format string igs по целевому выпуску; проверить единицы, оболочки и открытые границы.

Проверка: После импорта проверь соединения и замкнутость.

API [Document.export_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.export_data)

```python
export_data(file_name: Path, file_type: str, overwrite=False) -> None
```

CATIA COM: `Sub ExportData( CATBSTR fileName, CATBSTR format)`.


### 204 STL Export

**CATIA-204 · direct · P3**

Путь и stl; проверить качество тесселяции, единицы у получателя и доступность экспортера.

Проверка: Проверь масштаб, точность аппроксимации и единицы у получателя.

API [Document.export_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.export_data)

```python
export_data(file_name: Path, file_type: str, overwrite=False) -> None
```

CATIA COM: `Sub ExportData( CATBSTR fileName, CATBSTR format)`.


### 205 PDF Export

**CATIA-205 · direct · P3**

CATDrawing и pdf; проверить число листов, читаемость и масштаб.

Проверка: Открой итоговый PDF и проверь шрифты, линии и масштаб.

API [Document.export_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.export_data)

```python
export_data(file_name: Path, file_type: str, overwrite=False) -> None
```

CATIA COM: `Sub ExportData( CATBSTR fileName, CATBSTR format)`.


### 206 DXF Export

**CATIA-206 · direct · P3**

CATDrawing либо поддержанная развёртка и dxf; проверить слои и фактические длины после импорта.

Проверка: Проверь слои, единицы и отсутствие лишних линий.

API [Document.export_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.export_data)

```python
export_data(file_name: Path, file_type: str, overwrite=False) -> None
```

CATIA COM: `Sub ExportData( CATBSTR fileName, CATBSTR format)`.


### 207 Save Management

**CATIA-207 · workflow · P3**

Сохранение комплекта — граф зависимостей и проверка путей, не один SaveAs. Не закрывать/перезаписывать без явных параметров операции.

Проверка: Проверь реальные пути и открытие сборки из новой папки.

API [Document.save_as](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.save_as)

```python
save_as(file_name: Path, overwrite: bool=False) -> None
```

CATIA COM: `o Sub SaveAs(CATBSTR fileName)`.

API [Document.save](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/document.html#pycatia.in_interfaces.document.Document.save)

```python
save() -> None
```

CATIA COM: `o Sub Save()`.

API [Documents.open](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/documents.html#pycatia.in_interfaces.documents.Documents.open)

```python
open(file_name: Path) -> AnyDocument
```

CATIA COM: `o Func Open(CATBSTR iFileName) As Document`.

API [Product.products](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.products)

```python
property products: 'Products'
```

CATIA COM: `o Property Products() As Products`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


## Диагностика типичных ошибок

### 208 Pad не создаётся

**CATIA-208 · diagnostic · P0**

Собрать диагностику профиля и контекста; не менять длину Pad случайно и не обещать автоматическую починку.

Проверка: Не исправляй проблему случайным увеличением длины.

API [Sketch.evaluate](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.evaluate)

```python
evaluate() -> None
```

CATIA COM: `o Sub Evaluate()`.

API [Constraints.broken_constraints_count](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.broken_constraints_count)

```python
property broken_constraints_count: int
```

CATIA COM: `o Property BrokenConstraintsCount() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Part.is_up_to_date](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_up_to_date)

```python
is_up_to_date(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsUpToDate(AnyObject iObject) As boolean`.


### 209 Pocket ничего не вырезает

**CATIA-209 · diagnostic · P0**

Проверить направление, глубину, target Body и геометрическое пересечение профиля с solid.

Проверка: Отдельно проверь текущий Body.

API [Prism.direction_orientation](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.direction_orientation)

```python
property direction_orientation: int
```

CATIA COM: `o Property DirectionOrientation() As CatPrismOrientation`.

Свойство имеет setter.

API [Prism.first_limit](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/prism.html#pycatia.part_interfaces.prism.Prism.first_limit)

```python
property first_limit: Limit
```

CATIA COM: `o Property FirstLimit() As Limit`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Part.in_work_object](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.in_work_object)

```python
property in_work_object: AnyObject
```

CATIA COM: `o Property InWorkObject() As AnyObject`.

Свойство имеет setter.

API [SPAWorkbench.get_measurable](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/spa_workbench.html#pycatia.space_analyses_interfaces.spa_workbench.SPAWorkbench.get_measurable)

```python
get_measurable(i_measured_item: Reference) -> Measurable
```

CATIA COM: `o Func GetMeasurable(Reference iMeasuredItem) As Measurable`.


### 210 Эскиз переопределён

**CATIA-210 · diagnostic · P0**

Перечислить конфликтующие связи и последние изменения; удаление связей отдельная санкционированная операция.

Проверка: Не удаляй все ограничения сразу.

API [Constraint.status](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.status)

```python
property status: int
```

CATIA COM: `o Property Status() As CatConstraintStatus`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Constraints.broken_constraints_count](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.broken_constraints_count)

```python
property broken_constraints_count: int
```

CATIA COM: `o Property BrokenConstraintsCount() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Constraints.un_updated_constraints_count](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraints.html#pycatia.mec_mod_interfaces.constraints.Constraints.un_updated_constraints_count)

```python
property un_updated_constraints_count: int
```

CATIA COM: `o Property UnUpdatedConstraintsCount() As long`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 211 Эскиз двигается целиком

**CATIA-211 · diagnostic · P0**

Отсутствие broken constraints не доказывает полное определение. Для доступных DOF использовать отдельную подтверждённую диагностику/численную проверку.

Проверка: Размеры формы ещё не фиксируют её расположение.

API [Sketch.get_absolute_axis_data](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.get_absolute_axis_data)

```python
get_absolute_axis_data() -> tuple
```

CATIA COM: `o Sub GetAbsoluteAxisData(CATSafeArrayVariant oAxisData)`.

API [Constraint.status](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.status)

```python
property status: int
```

CATIA COM: `o Property Status() As CatConstraintStatus`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Sketch.constraints](https://pycatia.readthedocs.io/en/latest/api/pycatia/sketcher_interfaces/sketch.html#pycatia.sketcher_interfaces.sketch.Sketch.constraints)

```python
property constraints: Constraints
```

CATIA COM: `o Property Constraints() As Constraints`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.


### 212 Fillet не проходит

**CATIA-212 · diagnostic · P0**

Записать выбранные ребра, радиус и ошибку Update; не уменьшать инженерный радиус без разрешённого диапазона.

Проверка: Уменьшение радиуса — диагностика, а не всегда допустимое решение.

API [ConstRadEdgeFillet.radius](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/const_rad_edge_fillet.html#pycatia.part_interfaces.const_rad_edge_fillet.ConstRadEdgeFillet.radius)

```python
property radius: Length
```

CATIA COM: `o Property Radius() As Length`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Part.is_up_to_date](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_up_to_date)

```python
is_up_to_date(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsUpToDate(AnyObject iObject) As boolean`.

Класс настройки [Measurable](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 213 Shell не строится

**CATIA-213 · diagnostic · P0**

Проверить толщины, удаляемые грани и локальные радиусы; диагностический suppressed state не сохранять как успех.

Проверка: Попробуй диагностировать модель до мелких скруглений.

Класс настройки [Shell](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/shell.html#pycatia.part_interfaces.shell.Shell); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

API [Part.is_up_to_date](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_up_to_date)

```python
is_up_to_date(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsUpToDate(AnyObject iObject) As boolean`.

Класс настройки [Measurable](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.


### 214 Loft перекручивается

**CATIA-214 · diagnostic · P0**

Проверить порядок, направления и closing points сечений; сравнить промежуточные сечения.

Проверка: Добавление новых сечений может усилить проблему.

Класс настройки [Loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/part_interfaces/loft.html#pycatia.part_interfaces.loft.Loft); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

API [HybridShapeLoft.get_section_from_loft](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.get_section_from_loft)

```python
get_section_from_loft(i_rank: int, o_crv: Reference, o_ori: int, o_point: Reference) -> None
```

CATIA COM: `o Sub GetSectionFromLoft(long iRank, Reference oCrv, long oOri, Reference oPoint)`.

API [HybridShapeLoft.section_coupling](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_loft.html#pycatia.hybrid_shape_interfaces.hybrid_shape_loft.HybridShapeLoft.section_coupling)

```python
property section_coupling: int
```

CATIA COM: `o Property SectionCoupling() As long`.

Свойство имеет setter.


### 215 Join есть а solid нет

**CATIA-215 · diagnostic · P0**

Boundary — диагностическая геометрия, создаётся только в разрешённом временном контейнере; проверить замкнутость, manifold и self-intersections.

Проверка: Join и Close Surface решают разные задачи.

API [HybridShapeFactory.add_new_boundary_of_surface](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_factory.html#pycatia.hybrid_shape_interfaces.hybrid_shape_factory.HybridShapeFactory.add_new_boundary_of_surface)

```python
add_new_boundary_of_surface(surface: Reference) -> HybridShapeBoundary
```

CATIA COM: `o Func AddNewBoundaryOfSurface(Reference Surface) As HybridShapeBoundary`.

Класс настройки [HybridShapeAssemble](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_assemble.html#pycatia.hybrid_shape_interfaces.hybrid_shape_assemble.HybridShapeAssemble); получить существующий COM object, затем использовать wrapper. Доступные члены перечислены в словаре API.

API [Part.is_up_to_date](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/part.html#pycatia.mec_mod_interfaces.part.Part.is_up_to_date)

```python
is_up_to_date(i_object: AnyObject) -> bool
```

CATIA COM: `o Func IsUpToDate(AnyObject iObject) As boolean`.


### 216 Сборка скачет при Update

**CATIA-216 · diagnostic · P0**

Сравнить transforms до/после Update и конфликтующие constraints; не маскировать проблему произвольным Move.

Проверка: Ручное перемещение не устраняет причину.

API [Product.update](https://pycatia.readthedocs.io/en/latest/api/pycatia/product_structure_interfaces/product.html#pycatia.product_structure_interfaces.product.Product.update)

```python
update() -> None
```

CATIA COM: `o Sub Update()`.

API [Constraint.status](https://pycatia.readthedocs.io/en/latest/api/pycatia/mec_mod_interfaces/constraint.html#pycatia.mec_mod_interfaces.constraint.Constraint.status)

```python
property status: int
```

CATIA COM: `o Property Status() As CatConstraintStatus`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Position.get_components](https://pycatia.readthedocs.io/en/latest/api/pycatia/in_interfaces/position.html#pycatia.in_interfaces.position.Position.get_components)

```python
get_components() -> tuple
```

CATIA COM: `o Sub GetComponents(CATSafeArrayVariant oAxisComponentsArray)`.


### 217 Размер чертежа потерял ссылку

**CATIA-217 · diagnostic · P0**

Обновить вид и проверить status/link; fake dimension text запрещён как способ исправления привязки.

Проверка: Не подменяй неверный размер обычным текстом.

API [DrawingDimension.dim_status](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.dim_status)

```python
property dim_status: int
```

CATIA COM: `o Property DimStatus() As CatDimAnalyse`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [DrawingViewGenerativeBehavior.update](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html#pycatia.drafting_interfaces.drawing_view_generative_behavior.DrawingViewGenerativeBehavior.update)

```python
update() -> None
```

CATIA COM: `o Sub Update()`.

API [DrawingDimension.get_value](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_dimension.html#pycatia.drafting_interfaces.drawing_dimension.DrawingDimension.get_value)

```python
get_value() -> DrawingDimValue
```

CATIA COM: `o Func GetValue() As DrawingDimValue`.


### 218 Масса выглядит странно

**CATIA-218 · diagnostic · P0**

Сопоставить объём, плотность, units и состав включённых тел; массу без density считать непроверенной.

Проверка: Объём и масса — разные проверки.

API [Inertia.mass](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.mass)

```python
property mass: float
```

CATIA COM: `o Property Mass() As double`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

API [Inertia.density](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/inertia.html#pycatia.space_analyses_interfaces.inertia.Inertia.density)

```python
property density: float
```

CATIA COM: `o Property Density() As double`.

Свойство имеет setter.

API [Measurable.volume](https://pycatia.readthedocs.io/en/latest/api/pycatia/space_analyses_interfaces/measurable.html#pycatia.space_analyses_interfaces.measurable.Measurable.volume)

```python
property volume: float
```

CATIA COM: `Property Volume( ) As double`.

Свойство readonly в wrapper; возвращаемый объект может иметь собственные setters.

