# Реализация CATIA_AGENT_CODEX_PACKAGE — 2026-10-09

## Фактический статус

124 MCP tools; исходные 81 имени сохранены. 201 из 218 пунктов
имеют **ограниченный обработчик или диагностический путь**. Это НЕ означает
полную реализацию всех режимов этих пунктов. Остальные получают явный
`UNSUPPORTED_OPERATION` через `catia_capability_request` с причиной и research task.
Все 218 доступны через `catia_capability_status` (limit=218).

Backend raw pywin32, один STA-worker, document binding, server-local revision,
request journal. `.codex/config.toml`, transport и одиночный режим не менялись.
Все новые записи требуют document_id, expected_revision, request_id (создание
нового Drawing исключает обязательность старого document_id).

## Добавленные группы

Дополнение: `catia_profile_solids` создаёт последовательность обычных Pad/Pocket
из отдельных эскизов с индивидуальными глубинами. Все профили проверяются на
принадлежность целевому Body; после каждой фичи выполняются Update и чтение глубины.
Это отдельная геометрическая альтернатива, НЕ native Multi Pad/Multi Pocket:
пункты 056/057 по-прежнему помечены unsupported, но содержат ссылку на альтернативу.
В `catia_wireframe_surface` добавлены point_curve_distance,
point_curve_reference_distance/fraction, point_curve_direction,
point_plane_reference и point_surface_reference. Backend — соответствующие
`AddNewPointOnCurve*`, `AddNewPointOnPlaneWithReference`,
`AddNewPointOnSurfaceWithReference`. Координаты плоскости локальные, длины mm;
геометрия на Windows не проверена.

- `advanced_geometry.py`: Stiffener, face/tritangent/variable fillet, User Pattern,
  rotation/scaling/split, prism direction/second limit, thread, draft/shell faces,
  loft guides; point/line/plane, cylinder/sphere/helix, extract/boundary,
  extrapolation/healing/smoothing/remove/replace face, axis system.
- `sketch_operations.py`: polyline с общими вершинами, geometric transforms,
  ограниченные trim/break/chamfer/corner, формула R=D/2, equality параметров.
- `domains.py`: Product tree/occurrences, replacement, publications, metadata,
  BOM, contact, release-dependent FixTogether; Rule/Check/Law/design table,
  UDF/PowerCopy с finally cleanup; visibility без потери непустого выделения.
- `drafting.py`: новая Drawing/Sheet, front/isometric/projection/auxiliary,
  section/cut/detail/unfolded, clipping/broken/breakout, scale, text/leader/GDT,
  размеры/цепочки/baseline/tolerances, примитивы title block/center mark.
- `analysis_tools.py`, `com_arrays.py`: типизированные измерения, SAFEARRAY adapter,
  inertia/density, чтение каталога и назначение материала, Clash/Section/Mechanism,
  ограниченные diagnostics без автоматического ремонта.

## Важные границы

- `implemented_scoped` в таблице означает наличие обработчика, не GUI-equivalence.
- Sketch transforms создают НЕассоциативные копии линий/полных окружностей.
  Line-edit ограничен unconstrained sketch; исходные линии становятся construction
  только по явному аргументу. Spline trim/offset и перенос зависимостей не обещаны.
- Scaling, Affinity, Part translation/rotation реализованы с явными опорами;
  ориентация и реальные выходные габариты требуют Windows-проверки.
- Law создается, но автоматическая привязка закона к sweep не реализована.
- Generated section может иметь штриховку по настройкам CATIA; arbitrary hatch нет.
- Baseline/chained — обычные отдельные dimensions; CumulateMode не записывается.
- Sheetmetal cutout — только обычные Hole/Pocket, не native unfolded-aware Cutout.
  K factor — только явное редактирование существующего параметра шаблона.
- FixTogethers getter проверяется при обращении; при отсутствии — capability error.
- SAFEARRAY late binding может отвергаться конкретной CATIA; возвращается ошибка,
  не нули. Никаких VBA/execute_python обходов.
- Geometry Update не доказывает объем, касательность, правильную грань или ссылку
  размера. Diagnostic с `undetermined` не означает найденную причину неисправности.
- Имена материала плюс текущие индексы — проверка от случайного сдвига списка,
  не стабильный ID. Источник должен оставаться открытым и неизменным.
- Неуспех может оставить созданные объекты. Atomic rollback не обещан.

## Проверки

Короткий набор `tests/test_package_runtime.py tests/test_operation_groups.py`:
12 passed. Проверены schemas, исходные имена, binding/replay/partial-failure,
ось sketch, строгие mode contracts, все 218 статусов, отказ unsupported,
порядок constructor/append/update для point center, CreateProgram для Rule,
finally cleanup InstanceFactory при ошибке, остановка последовательности Pad
после частичной ошибки и честный статус альтернативы Multi Pad.
Это НЕ тест всех новых COM branches.
`test_server.py`: 124 tools, inspection 13. `check_mcp_transport.py`: реальный
stdio discovery 124/13, без вызовов CATIA. Full test suite не запускался.
Для каждой capability: `live_tested=false`; capability-level offline validation
не заявлена только на основании этих smoke checks.

## Проверка в Windows

После переноса обновленного checkout:

```powershell
.\INSTALL.cmd
.\DIAGNOSE.cmd
.\START_CATIA_AI.cmd
```

В новом Codex-сеансе проверить доступ к 124 tools. На новых несохраненных документах:
1. Polyline/diameter/transform → закрыть sketch → Pad/Pocket; сверить mm и объем.
2. Stiffener/fillets/loft/second limit; ошибочная геометрия не должна давать success.
3. GSD plane/point/cylinder/helix/mean/heal; проверить orientation и результат Update.
4. Product occurrences/contact/FixTogether, публикации и DMU с лицензией.
5. Drawing views/section/breakout/dimensions: проверить исходный документ не изменен,
   размеры связаны с правильными элементами; обновить исходную модель вручную и
   проверить associativity. Не сохранять/экспортировать без явного пути.
6. Материал/inertia на аналитическом кубе; сверить kg, m, mm и density sentinel.
7. Rule/design table/template: лицензия, readback, частичная ошибка и отсутствие дубля
   при повторном request_id. Выходные массивы проверить на известных координатах.

## Источники уточнений

Основная evidence — JSON/Markdown внутри `CATIA_AGENT_CODEX_PACKAGE`.
Дополнительно проверены [Drawing GenerativeBehavior](https://pycatia.readthedocs.io/en/latest/api/pycatia/drafting_interfaces/drawing_view_generative_behavior.html),
[Healing](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_healing.html),
[официальные enum definitions](https://github.com/evereux/pycatia/blob/master/pycatia/enumeration/enumeration_types.py).
Для Part transforms дополнительно сверены
[HybridShapeTranslate](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_translate.html)
и [HybridShapeAffinity](https://pycatia.readthedocs.io/en/latest/api/pycatia/hybrid_shape_interfaces/hybrid_shape_affinity.html).
Это проверка документации, НЕ запуск CATIA.

## Матрица всех 218 пунктов

В колонке API приведены первые bindings исходного каталога; полный список и
ограничения — в CATIA_AGENT_API_CATALOG.md. Точные поддержанные аргументы — в
JSON Schema указанного tool и соответствующем handler. Везде live=false.

| ID | Возможность | Статус | Обработчики | API из спецификации |
|---|---|---|---|---|
| CATIA-001 | Part и CATPart | implemented_scoped | catia_new_part | Add, Part |
| CATIA-002 | Body и PartBody | implemented_scoped | catia_create_container | Add, Bodies |
| CATIA-003 | Geometrical Set | implemented_scoped | catia_create_container | Add, HybridBodies |
| CATIA-004 | Ordered Geometrical Set | implemented_scoped | catia_create_container | Add, OrderedGeometricalSets |
| CATIA-005 | Define In Work Object | implemented_scoped | catia_feature_state | InWorkObject |
| CATIA-006 | Update | implemented_scoped | catia_update_part | Update, UpdateObject |
| CATIA-007 | Activate и Deactivate | implemented_scoped | catia_feature_state | Activate, Inactivate |
| CATIA-008 | Hide и Show | implemented_scoped | catia_visibility | Clear, Add |
| CATIA-009 | Parents и Children | implemented_scoped | catia_list_objects | Parent, Name |
| CATIA-010 | Change Sketch Support | unsupported: Прямой setter Sketch.support отсутствует в pycatia 0.10.1. Изменение абсолютных осей не доказывает смену опоры. Пересоздание sketch требует переноса constraints и зависимых features; отдельная операция с явным риском потери ссылок. | catia_capability_request | SetAbsoluteAxisData, GetAbsoluteAxisData |
| CATIA-011 | Sketch | implemented_scoped | catia_create_sketch, catia_close_sketch | Add, OpenEdition |
| CATIA-012 | Positioned Sketch | implemented_scoped | catia_create_sketch | Add, SetAbsoluteAxisData |
| CATIA-013 | Point | implemented_scoped | catia_sketch_point | CreatePoint |
| CATIA-014 | Line | implemented_scoped | catia_sketch_line | CreateLine |
| CATIA-015 | Profile | implemented_scoped | catia_sketch_profile | CreateLine, CreateCircle |
| CATIA-016 | Rectangle и Centered Rectangle | implemented_scoped | catia_sketch_rectangle, catia_sketch_centered_rectangle | CreateLine, AddBiEltCst |
| CATIA-017 | Circle | implemented_scoped | catia_sketch_circle | CreateClosedCircle |
| CATIA-018 | Arc | implemented_scoped | catia_sketch_arc | CreateCircle |
| CATIA-019 | Ellipse | implemented_scoped | catia_sketch_ellipse | CreateEllipse, CreateClosedEllipse |
| CATIA-020 | Spline | implemented_scoped | catia_sketch_spline | CreateControlPoint, CreateSpline |
| CATIA-021 | Axis и Construction Geometry | implemented_scoped | catia_sketch_set_axis | Construction, CenterLine |
| CATIA-022 | Corner | implemented_scoped | catia_sketch_line_edit | CreateCircle, CreateLine |
| CATIA-023 | Chamfer | implemented_scoped | catia_sketch_line_edit | CreateLine, SetData |
| CATIA-024 | Trim и Quick Trim | implemented_scoped | catia_sketch_line_edit | CreateLine, CreateCircle |
| CATIA-025 | Break | implemented_scoped | catia_sketch_line_edit | CreateLine, CreateCircle |
| CATIA-026 | Mirror | implemented_scoped | catia_sketch_transform | CreateLine, CreateClosedCircle |
| CATIA-027 | Symmetry | implemented_scoped | catia_sketch_transform | AddTriEltCst, CreateLine |
| CATIA-028 | Translate и Rotate | implemented_scoped | catia_sketch_transform | SetData, SetData |
| CATIA-029 | Scale | implemented_scoped | catia_sketch_transform | SetData, SetData |
| CATIA-030 | Offset | implemented_scoped | catia_sketch_transform | CreateLine, CreateCircle |
| CATIA-031 | Project 3D Elements | implemented_scoped | catia_sketch_import_geometry | CreateProjection, CreateProjections |
| CATIA-032 | Intersect 3D Elements | implemented_scoped | catia_sketch_import_geometry | CreateIntersection, CreateIntersections |
| CATIA-033 | Sketch Analysis | implemented_scoped | catia_sketch_diagnose | Evaluate, BrokenConstraintsCount |
| CATIA-034 | Length и Distance | implemented_scoped | catia_sketch_constraint | AddMonoEltCst, AddBiEltCst |
| CATIA-035 | Radius и Diameter | implemented_scoped | catia_sketch_constraint, catia_sketch_relation | AddMonoEltCst, Dimension |
| CATIA-036 | Angle | implemented_scoped | catia_sketch_constraint | AddBiEltCst, Dimension |
| CATIA-037 | Coincidence | implemented_scoped | catia_sketch_constraint | AddBiEltCst |
| CATIA-038 | Horizontal и Vertical | implemented_scoped | catia_sketch_constraint | AddMonoEltCst |
| CATIA-039 | Parallelism и Perpendicularity | implemented_scoped | catia_sketch_constraint | AddBiEltCst |
| CATIA-040 | Tangency | implemented_scoped | catia_sketch_constraint | AddBiEltCst |
| CATIA-041 | Concentricity | implemented_scoped | catia_sketch_constraint | AddBiEltCst |
| CATIA-042 | Symmetry | implemented_scoped | catia_sketch_constraint | AddTriEltCst |
| CATIA-043 | Equality | implemented_scoped | catia_sketch_relation | AddBiEltCst, CreateFormula |
| CATIA-044 | Fix | implemented_scoped | catia_sketch_constraint | AddMonoEltCst |
| CATIA-045 | Driving и Reference Dimension | implemented_scoped | catia_sketch_constraint | Mode, Dimension |
| CATIA-046 | Pad | implemented_scoped | catia_pad | AddNewPad, Pad |
| CATIA-047 | Pocket | implemented_scoped | catia_pocket | AddNewPocket, Pocket |
| CATIA-048 | Shaft | implemented_scoped | catia_shaft | AddNewShaft, RevoluteAxis |
| CATIA-049 | Groove | implemented_scoped | catia_groove | AddNewGroove, RevoluteAxis |
| CATIA-050 | Hole | implemented_scoped | catia_hole | AddNewHoleFromSketch, AddNewHoleFromPoint |
| CATIA-051 | Rib | implemented_scoped | catia_swept_solid | AddNewRib, Rib |
| CATIA-052 | Slot | implemented_scoped | catia_swept_solid | AddNewSlot, Slot |
| CATIA-053 | Stiffener | implemented_scoped | catia_solid_operation | AddNewStiffener, Thickness |
| CATIA-054 | Multi Sections Solid | implemented_scoped | catia_solid_loft, catia_feature_options | AddNewLoft, HybridShape |
| CATIA-055 | Removed Multi Sections Solid | implemented_scoped | catia_solid_loft, catia_feature_options | AddNewRemovedLoft, HybridShape |
| CATIA-056 | Multi Pad | unsupported: Прямой Multi Pad в ShapeFactory не найден. Несколько обычных Pad можно предложить как отдельный алгоритм, но это другое feature tree и не эквивалент UI Multi Pad. | catia_capability_request |  |
| CATIA-057 | Multi Pocket | unsupported: Прямой Multi Pocket в ShapeFactory не найден. Последовательность Pocket допустима только как явно согласованный заменяющий алгоритм. | catia_capability_request |  |
| CATIA-058 | Dimension | implemented_scoped | catia_pad, catia_pocket | FirstLimit, LimitMode |
| CATIA-059 | Up to Next | implemented_scoped | catia_pad, catia_pocket | FirstLimit, LimitMode |
| CATIA-060 | Up to Last | implemented_scoped | catia_pad, catia_pocket | FirstLimit, LimitMode |
| CATIA-061 | Up to Plane и Up to Surface | implemented_scoped | catia_pad, catia_pocket | FirstLimit, LimitMode |
| CATIA-062 | Reverse Direction | implemented_scoped | catia_pad, catia_pocket, catia_feature_options | DirectionOrientation, SetDirection |
| CATIA-063 | Second Limit и Mirrored Extent | implemented_scoped | catia_pad, catia_feature_options | SecondLimit, IsSymmetric |
| CATIA-064 | Simple Hole | implemented_scoped | catia_hole | Type, Diameter |
| CATIA-065 | Counterbored Hole | implemented_scoped | catia_hole | Type, HeadDiameter |
| CATIA-066 | Countersunk Hole | implemented_scoped | catia_hole | Type, HeadDiameter |
| CATIA-067 | Threaded Hole и Thread Tap | implemented_scoped | catia_feature_options | ThreadingMode, HoleThreadDescription |
| CATIA-068 | Edge Fillet | implemented_scoped | catia_fillet | AddNewEdgeFilletWithConstantRadius, AddObjectToFillet |
| CATIA-069 | Variable Radius Fillet | implemented_scoped | catia_solid_operation | AddNewEdgeFilletWithVaryingRadius, VarRadEdgeFillet |
| CATIA-070 | Face Face Fillet | implemented_scoped | catia_solid_operation | AddNewFaceFillet, FaceFillet |
| CATIA-071 | Tritangent Fillet | implemented_scoped | catia_solid_operation | AddNewTritangentFillet, TritangentFillet |
| CATIA-072 | Chamfer | implemented_scoped | catia_chamfer | AddNewChamfer, Chamfer |
| CATIA-073 | Shell | implemented_scoped | catia_shell, catia_feature_options | AddNewShell, AddFaceToRemove |
| CATIA-074 | Thickness | implemented_scoped | catia_thickness | AddNewThickness, Thickness |
| CATIA-075 | Draft | implemented_scoped | catia_draft, catia_feature_options | AddNewDraft, DraftDomains |
| CATIA-076 | Thick Surface | implemented_scoped | catia_gsd_thick_surface | AddNewThickSurface, ThickSurface |
| CATIA-077 | Close Surface | implemented_scoped | catia_gsd_close_surface | AddNewCloseSurface |
| CATIA-078 | Rectangular Pattern | implemented_scoped | catia_rect_pattern | AddNewRectPattern, RectPattern |
| CATIA-079 | Circular Pattern | implemented_scoped | catia_circ_pattern | AddNewCircPattern, CircPattern |
| CATIA-080 | User Pattern | implemented_scoped | catia_solid_operation | AddNewUserPattern, UserPattern |
| CATIA-081 | Mirror | implemented_scoped | catia_mirror | AddNewMirror |
| CATIA-082 | Translation и Rotation | implemented_scoped | catia_solid_operation | AddNewTranslate2, Translate |
| CATIA-083 | Scaling и Affinity | implemented_scoped | catia_solid_operation | AddNewScaling, AddNewAffinity2 |
| CATIA-084 | Boolean Add | implemented_scoped | catia_boolean | AddNewAdd |
| CATIA-085 | Boolean Remove | implemented_scoped | catia_boolean | AddNewRemove |
| CATIA-086 | Boolean Intersect | implemented_scoped | catia_boolean | AddNewIntersect |
| CATIA-087 | Boolean Assemble | implemented_scoped | catia_boolean | AddNewAssemble |
| CATIA-088 | Split Solid | implemented_scoped | catia_solid_operation | AddNewSplit |
| CATIA-089 | Point Coordinates | implemented_scoped | catia_reference_point | AddNewPointCoord |
| CATIA-090 | Point On Curve | implemented_scoped | catia_reference_point | AddNewPointOnCurveFromPercent, AddNewPointOnCurveFromDistance |
| CATIA-091 | Point On Plane | implemented_scoped | catia_reference_point | AddNewPointOnPlane, AddNewPointOnPlaneWithReference |
| CATIA-092 | Point On Surface | implemented_scoped | catia_wireframe_surface | AddNewPointOnSurface, AddNewPointOnSurfaceWithReference |
| CATIA-093 | Circle Sphere Center | implemented_scoped | catia_wireframe_surface | AddNewPointCenter |
| CATIA-094 | Point Between | implemented_scoped | catia_reference_point | AddNewPointBetween |
| CATIA-095 | Line Point Point | implemented_scoped | catia_gsd_line | AddNewLinePtPt |
| CATIA-096 | Line Point Direction | implemented_scoped | catia_wireframe_surface | AddNewDirectionByCoord, AddNewLinePtDir |
| CATIA-097 | Line Normal to Surface | implemented_scoped | catia_wireframe_surface | AddNewLineNormal |
| CATIA-098 | Line Tangent to Curve | implemented_scoped | catia_wireframe_surface | AddNewLineTangency |
| CATIA-099 | Axis System | implemented_scoped | catia_axis_system | Add, PutOrigin |
| CATIA-100 | Offset from Plane | implemented_scoped | catia_reference_plane | AddNewPlaneOffset |
| CATIA-101 | Parallel through Point | implemented_scoped | catia_reference_plane | AddNewPlaneOffsetPt |
| CATIA-102 | Angle to Plane | implemented_scoped | catia_wireframe_surface | AddNewPlaneAngle |
| CATIA-103 | Through Three Points | implemented_scoped | catia_reference_plane | AddNewPlane3Points |
| CATIA-104 | Through Two Lines | implemented_scoped | catia_reference_plane | AddNewPlane2Lines |
| CATIA-105 | Through Point and Line | implemented_scoped | catia_reference_plane | AddNewPlane1Line1Pt |
| CATIA-106 | Through Planar Curve | implemented_scoped | catia_wireframe_surface | AddNewPlane1Curve |
| CATIA-107 | Normal to Curve | implemented_scoped | catia_reference_plane | AddNewPlaneNormal |
| CATIA-108 | Tangent to Surface | implemented_scoped | catia_reference_plane | AddNewPlaneTangent |
| CATIA-109 | Equation | implemented_scoped | catia_reference_plane | AddNewPlaneEquation |
| CATIA-110 | Mean through Points | implemented_scoped | catia_wireframe_surface | AddNewPlaneMean |
| CATIA-111 | Extrude Surface | implemented_scoped | catia_gsd_extrude | AddNewExtrude |
| CATIA-112 | Revolution Surface | implemented_scoped | catia_gsd_revolve | AddNewRevol |
| CATIA-113 | Sweep | implemented_scoped | catia_gsd_sweep | AddNewSweepExplicit, HybridShapeSweepExplicit |
| CATIA-114 | Multi Sections Surface | implemented_scoped | catia_gsd_multi_section_surface | AddNewLoft, AddSectionToLoft |
| CATIA-115 | Fill | implemented_scoped | catia_gsd_fill | AddNewFill, AddBound |
| CATIA-116 | Blend | implemented_scoped | catia_gsd_blend | AddNewBlend, SetCurve |
| CATIA-117 | Offset Surface | implemented_scoped | catia_gsd_offset_surface | AddNewOffset |
| CATIA-118 | Cylinder и Sphere | implemented_scoped | catia_wireframe_surface | AddNewCylinder, AddNewSphere |
| CATIA-119 | Helix | implemented_scoped | catia_wireframe_surface | AddNewHelix |
| CATIA-120 | Law driven geometry | implemented_scoped | catia_knowledgeware | AddNewIntegratedLaw, AddNewLawDistProj |
| CATIA-121 | Extract | implemented_scoped | catia_wireframe_surface | AddNewExtract, PropagationType |
| CATIA-122 | Boundary | implemented_scoped | catia_wireframe_surface | AddNewBoundaryOfSurface, AddNewBoundary |
| CATIA-123 | Join | implemented_scoped | catia_gsd_join | AddNewJoin, AddElement |
| CATIA-124 | Split Surface | implemented_scoped | catia_gsd_split | AddNewHybridSplit |
| CATIA-125 | Trim Surfaces | implemented_scoped | catia_gsd_trim | AddNewHybridTrim |
| CATIA-126 | Intersection | implemented_scoped | catia_gsd_intersection | AddNewIntersection |
| CATIA-127 | Projection | implemented_scoped | catia_gsd_project | AddNewProject, HybridShapeProject |
| CATIA-128 | Extrapolate | implemented_scoped | catia_wireframe_surface | AddNewExtrapolLength, AddNewExtrapolUntil |
| CATIA-129 | Healing | implemented_scoped | catia_wireframe_surface | AddNewHealing, HybridShapeHealing |
| CATIA-130 | Curve Smooth | implemented_scoped | catia_wireframe_surface | AddNewCurveSmooth, HybridShapeCurveSmooth |
| CATIA-131 | Remove Face и Replace Face | implemented_scoped | catia_wireframe_surface | AddNewRemoveFace, AddNewReplaceFace |
| CATIA-132 | Existing Component | implemented_scoped | catia_add_component | AddComponentsFromFiles |
| CATIA-133 | New Part | implemented_scoped | catia_add_new_part | AddNewComponent |
| CATIA-134 | New Product | implemented_scoped | catia_assembly_operation | AddNewProduct |
| CATIA-135 | Component Instance | implemented_scoped | catia_assembly_operation | AddComponent |
| CATIA-136 | Replace Component | implemented_scoped | catia_assembly_operation | ReplaceComponent, ReplaceProduct |
| CATIA-137 | Publication | implemented_scoped | catia_assembly_operation | Publications, Add |
| CATIA-138 | Design in Context | unsupported: Occurrence-aware external copy/link workflow not confirmed; publication alone is not Design in Context. | catia_capability_request | CreateReferenceFromName, CreateReferenceFromObject |
| CATIA-139 | Design Mode и Visualization Mode | implemented_scoped | catia_assembly_operation | ApplyWorkMode |
| CATIA-140 | Part Number и Properties | implemented_scoped | catia_assembly_operation | PartNumber, Revision |
| CATIA-141 | BOM | implemented_scoped | catia_assembly_operation | ExtractBOM |
| CATIA-142 | Fix Component | implemented_scoped | catia_fix_constraint | Connections, AddMonoEltCst |
| CATIA-143 | Coincidence | implemented_scoped | catia_coincidence_constraint | Connections, AddBiEltCst |
| CATIA-144 | Contact | implemented_scoped | catia_assembly_operation | Connections, AddBiEltCst |
| CATIA-145 | Offset | implemented_scoped | catia_offset_constraint | AddBiEltCst, Dimension |
| CATIA-146 | Angle | implemented_scoped | catia_angle_constraint | AddBiEltCst, Dimension |
| CATIA-147 | Fix Together | implemented_scoped | catia_assembly_operation | Add, AddProduct |
| CATIA-148 | Manipulation и Move | implemented_scoped | catia_move_component | Move, Apply |
| CATIA-149 | Clash и Clearance | implemented_scoped | catia_dmu | GetTechnologicalObject, Add |
| CATIA-150 | Sectioning | implemented_scoped | catia_dmu | GetTechnologicalObject, Add |
| CATIA-151 | DMU Kinematics | implemented_scoped | catia_dmu | GetTechnologicalObject, Add |
| CATIA-152 | Front View | implemented_scoped | catia_drawing_view | Add, GenerativeBehavior |
| CATIA-153 | Projection View | implemented_scoped | catia_drawing_view | DefineProjectionView |
| CATIA-154 | Isometric View | implemented_scoped | catia_drawing_view | DefineIsometricView |
| CATIA-155 | Auxiliary View | implemented_scoped | catia_drawing_view | DefineAuxiliaryView |
| CATIA-156 | Section View | implemented_scoped | catia_drawing_view | DefineSectionView |
| CATIA-157 | Section Cut | implemented_scoped | catia_drawing_view | DefineSectionView |
| CATIA-158 | Offset и Aligned Section | implemented_scoped | catia_drawing_view | DefineSectionView |
| CATIA-159 | Detail View | implemented_scoped | catia_drawing_view | DefineCircularDetailView, DefinePolygonalDetailView |
| CATIA-160 | Clipping View | implemented_scoped | catia_drawing_edit | DefineCircularClippingView, DefinePolygonalClippingView |
| CATIA-161 | Broken View | implemented_scoped | catia_drawing_edit | DefineBrokenView |
| CATIA-162 | Breakout View | implemented_scoped | catia_drawing_edit | DefineBreakout |
| CATIA-163 | Unfolded View | implemented_scoped | catia_drawing_view | DefineUnfoldedView |
| CATIA-164 | Length и Distance Dimensions | implemented_scoped | catia_drawing_dimension | Add, Add2 |
| CATIA-165 | Radius Diameter Angle | implemented_scoped | catia_drawing_dimension | Add, Add2 |
| CATIA-166 | Chained Dimensions | implemented_scoped | catia_drawing_dimension_series | Add, MoveValue |
| CATIA-167 | Cumulated и Baseline Dimensions | implemented_scoped | catia_drawing_dimension_series | Add, CumulateMode |
| CATIA-168 | Center Line и Center Mark | implemented_scoped | catia_drawing_annotation | Factory2D, CreateLine |
| CATIA-169 | Text with Leader | implemented_scoped | catia_drawing_annotation | Add, Leaders |
| CATIA-170 | Hatching и Area Fill | implemented_scoped | catia_drawing_view | DefineSectionView |
| CATIA-171 | Dimension Tolerances | implemented_scoped | catia_drawing_dimension | SetTolerances, GetTolerances |
| CATIA-172 | Datum и Geometrical Tolerance | implemented_scoped | catia_drawing_annotation | GDTs, Add |
| CATIA-173 | Surface Finish Symbol | unsupported: Прямой Drafting Surface Finish Symbol API не найден в просмотренном наборе. 3D FTA Roughness не эквивалентен 2D символу; не выдавать текстовый суррогат за semantic annotation. | catia_capability_request |  |
| CATIA-174 | Sheet Scale и View Scale | implemented_scoped | catia_drawing_edit | Scale, Scale |
| CATIA-175 | Sheet Background и Title Block | implemented_scoped | catia_drawing_annotation | Views, Item |
| CATIA-176 | Sheet Metal Parameters | unsupported: Параметры доступны как generic Parameters, но dedicated Sheet Metal Parameters factory в этом API-наборе не найден. Требуется проверенный template либо другой лицензированный Automation API. | catia_capability_request | Parameters |
| CATIA-177 | Wall | unsupported: Wall constructor листового металла не подтверждён; Pad не является эквивалентом. | catia_capability_request |  |
| CATIA-178 | Wall on Edge | unsupported: Wall on Edge constructor не подтверждён; шаблон PowerCopy допустим только после отдельной проверки входов и развёртки. | catia_capability_request |  |
| CATIA-179 | Bend | unsupported: Sheetmetal Bend constructor не подтверждён; поверхности и fillet не заменяют sheetmetal semantics. | catia_capability_request |  |
| CATIA-180 | Bend from Flat | unsupported: Bend from Flat constructor не подтверждён; исследовать template/recorded macro в конкретной CATIA. | catia_capability_request |  |
| CATIA-181 | Flange | unsupported: Sheetmetal Flange constructor не подтверждён в просмотренном pycatia API. | catia_capability_request |  |
| CATIA-182 | Hem | unsupported: Sheetmetal Hem constructor не подтверждён в просмотренном pycatia API. | catia_capability_request |  |
| CATIA-183 | Cutout и Hole | implemented_scoped | catia_hole, catia_pocket | AddNewHoleFromSketch, AddNewPocket |
| CATIA-184 | Corner Relief | unsupported: Corner Relief constructor не подтверждён. Не автоматически заменять generic Pocket без проверки развертки. | catia_capability_request |  |
| CATIA-185 | Fold и Unfold | unsupported: Sheetmetal Fold/Unfold не подтверждён. HybridShapeFactory.add_new_unfold относится к GSD и не доказывает эквивалентность этой команде. | catia_capability_request |  |
| CATIA-186 | Bend Allowance и K Factor | implemented_scoped | catia_set_parameter | Item, ValuateFromString |
| CATIA-187 | Bead и Stamp | unsupported: Sheetmetal Bead/Stamp constructors не подтверждены; не придумывать add_new_bead/add_new_stamp. | catia_capability_request |  |
| CATIA-188 | Parameters | implemented_scoped | catia_create_parameter, catia_set_parameter | CreateDimension, CreateReal |
| CATIA-189 | Formula | implemented_scoped | catia_create_formula, catia_knowledgeware | CreateFormula, Modify |
| CATIA-190 | Design Table | implemented_scoped | catia_knowledgeware | CreateDesignTable, AddAssociation |
| CATIA-191 | Rule | implemented_scoped | catia_knowledgeware | CreateProgram, Rule |
| CATIA-192 | Check | implemented_scoped | catia_knowledgeware | CreateCheck, Check |
| CATIA-193 | PowerCopy | implemented_scoped | catia_template_instance | GetCustomerFactory, BeginInstanceFactory |
| CATIA-194 | User Feature | implemented_scoped | catia_template_instance | AddInstance, InstanceFactory |
| CATIA-195 | Publication | implemented_scoped | catia_assembly_operation | Add, SetDirect |
| CATIA-196 | Macro и CATScript | unsupported: Arbitrary scripts forbidden; no audited fixed-contract macro supplied. | catia_capability_request | ExecuteScript, SystemService |
| CATIA-197 | pycatia | unsupported: Infrastructure, not a geometry command. Server uses raw pywin32 without mixing wrappers. | catia_capability_request | Application, Documents |
| CATIA-198 | Measure Item | implemented_scoped | catia_measure_object, catia_measure_exact | GetMeasurable, Measurable |
| CATIA-199 | Measure Between | implemented_scoped | catia_measure_distance, catia_measure_exact | GetMinimumDistance, GetAngleBetween |
| CATIA-200 | Measure Inertia | implemented_scoped | catia_get_inertia, catia_measure_exact | GetTechnologicalObject, Mass |
| CATIA-201 | Apply Material | implemented_scoped | catia_material | ApplyMaterialOnBody, ApplyMaterialOnPart |
| CATIA-202 | STEP Export | implemented_scoped | catia_export | ExportData |
| CATIA-203 | IGES Export | implemented_scoped | catia_export | ExportData |
| CATIA-204 | STL Export | implemented_scoped | catia_export | ExportData |
| CATIA-205 | PDF Export | implemented_scoped | catia_export | ExportData |
| CATIA-206 | DXF Export | implemented_scoped | catia_export | ExportData |
| CATIA-207 | Save Management | implemented_scoped | catia_save_document | SaveAs, Save |
| CATIA-208 | Pad не создаётся | diagnostic_scoped | catia_diagnose_geometry | Evaluate, BrokenConstraintsCount |
| CATIA-209 | Pocket ничего не вырезает | diagnostic_scoped | catia_pocket, catia_diagnose_geometry | DirectionOrientation, FirstLimit |
| CATIA-210 | Эскиз переопределён | diagnostic_scoped | catia_sketch_diagnose, catia_diagnose_geometry | Status, BrokenConstraintsCount |
| CATIA-211 | Эскиз двигается целиком | diagnostic_scoped | catia_diagnose_geometry | GetAbsoluteAxisData, Status |
| CATIA-212 | Fillet не проходит | diagnostic_scoped | catia_diagnose_geometry | Radius, IsUpToDate |
| CATIA-213 | Shell не строится | diagnostic_scoped | catia_diagnose_geometry | Shell, IsUpToDate |
| CATIA-214 | Loft перекручивается | diagnostic_scoped | catia_diagnose_geometry | Loft, GetSectionFromLoft |
| CATIA-215 | Join есть а solid нет | diagnostic_scoped | catia_diagnose_geometry | AddNewBoundaryOfSurface, HybridShapeAssemble |
| CATIA-216 | Сборка скачет при Update | diagnostic_scoped | catia_diagnose_geometry | Update, Status |
| CATIA-217 | Размер чертежа потерял ссылку | diagnostic_scoped | catia_diagnose_geometry | DimStatus, Update |
| CATIA-218 | Масса выглядит странно | diagnostic_scoped | catia_get_inertia, catia_diagnose_geometry | Mass, Density |
