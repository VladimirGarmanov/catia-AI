# Patterns: исправления и проверка на Windows

Проверены все существующие пути: `catia_rect_pattern`, `catia_circ_pattern`,
rectangular/circular в `catia_part_design_advanced`, их `_list` и `surfacic_`
варианты, `surfacic_user_pattern`, `user_pattern_list` и обычный `user_pattern`
в `catia_solid_operation`. Это аудит кода и offline-контрактов; живой CATIA
на Mac нет.

## Как задавать

- Предпочитайте `feature_handle`, `body_handle` и handles опор, полученные
  из текущей модели/выделения. В старых двух инструментах `feature_name`
  остаётся альтернативой handle: имя должно быть уникальным в целевом Body.
- В `catia_rect_pattern` передайте оба `first_direction_handle` и
  `second_direction_handle`, либо выделите две опоры в этом порядке.
  Прямая, прямолинейное ребро или плоская грань задают направление.
  Две опоры нужны и для одного ряда; второе направление в этом случае
  имеет `dir2_count=1`, `dir2_spacing=0`.
- В `catia_circ_pattern` передайте `center_handle` и `axis_handle`, либо
  выделите точку/вершину, затем ось. Осью может служить прямая, прямое ребро,
  плоскость либо цилиндрическая/плоская грань. Геометрическую пригодность
  точной Reference проверяет CATIA, сервер не угадывает её по имени.
- Оба handle опор задаются вместе. При отсутствии выбранной Reference
  родительская фича не подставляется. Selection handles истекают после
  изменения геометрии или обновления контекста; перечитайте выделение.
- Количества включают исходную фичу. Для rectangular/circular допустимо
  1..1000 по направлению и 2..10000 всего. Нулевой линейный шаг допустим
  только для направления с одним экземпляром. Для изменения направления
  используйте `dir1_forward`/`dir2_forward` либо `axis_forward`, а не отрицательный шаг.
- Четыре экземпляра на полном круге имеют шаг 90°, а не 120°.
  В `catia_circ_pattern` отсутствие `angular_spacing` задаёт полный круг.
  В advanced circular режимах `complete_crown=true` переопределяет
  `angular_spacing_deg` значением `360/angular_count`.
- `keep_parallel=true` сохраняет параллельность копий; `false` вращает их
  вокруг оси. Для старого `catia_circ_pattern` сохранён прежний default=true.
  Для проверки используйте несимметричную фичу: круглая дырка не показывает
  различие ориентаций. Формулировки CAA для аргумента конструктора и свойства
  `RadialAlignment` неоднозначны; последнее возвращается как native raw flag,
  геометрическая ориентация не объявляется проверенной по этому флагу.
- User pattern принимает явные positioning sketch и anchor. Обычный solid
  и list pattern отвергают фичи другого Body и повторяющиеся list seeds.
  `_list` API в CAA помечены V5R8 Only и требуют `allow_legacy_v5r8_api=true`;
  их отказ не запускает альтернативный конструктор автоматически.

## Что теперь проверяет сервер

После создания задаётся явный режим распределения и размерные параметры
в mm/deg, затем Update и readback количеств, активных шагов, seed positions,
направлений-флагов и общего угла. Ответ содержит реальные прочитанные значения.
Несовпадение — `POSTCONDITION_FAILED`; недоступный readback —
`POSTCONDITION_UNAVAILABLE`. Созданный объект остаётся в модели и перечисляется
в recovery-ответе: сначала осмотрите его, не повторяйте создание вслепую.

Количество в repartition не доказывает число отдельных BRep-копий, отсутствие
перекрытия или правильность выбранной оси. `geometry_verified=false` сохраняется.
У UserPattern нет документированного `InstancesCount`: проверяется anchor,
по возможности positioning sketch, но `actual_instances=null`.
Для list pattern отдельная проверка копирования **всех** seed-фич ещё нужна.

## Минимальная живая проверка

После `UPDATE.cmd` закройте старую AI-сессию и запустите `START_AI.cmd`.
На **новой несохранённой детали** с основанием и небольшим несимметричным Pad:

1. Rectangular 3×2 с шагами 10×20 mm: сравните расположение шести экземпляров
   и readback; отдельно проверьте 3×1 с нулевым неиспользуемым шагом.
2. Circular 4×90° вокруг явно выбранной цилиндрической грани/оси:
   сравните `keep_parallel=true/false` и `axis_forward=true/false`.
3. Advanced: source в середине ряда, дополнительный radial ряд, поворот
   всего распределения, complete crown с заведомо другим входным шагом.
4. User: positioning sketch из известных точек, явный anchor; сравните
   все положения и число фактических копий вручную.
5. В отдельной тестовой детали: surfacic rectangular/circular/user и
   list-варианты с двумя различимыми seeds (если релиз предоставляет API).
6. При ошибке Update/readback убедитесь, что ответ — failure с созданным
   handle, без второго pattern и без автоматического удаления.

Не сохранять/не экспортировать без отдельной команды и пути. Ни один из этих
живых сценариев ещё не подтверждён на Windows.

Контракты: CAA V5 Automation, зеркало документации Dassault —
[ShapeFactory](https://catiadesign.org/_doc/V5Automation/generated/interfaces/PartInterfaces/interface_ShapeFactory_20269.htm),
[RectPattern](https://catiadesign.org/_doc/V5Automation/generated/interfaces/PartInterfaces/interface_RectPattern_19102.htm),
[CircPattern](https://catiadesign.org/_doc/V5Automation/generated/interfaces/PartInterfaces/interface_CircPattern_19085.htm),
[UserPattern](https://catiadesign.org/_doc/V5Automation/generated/interfaces/PartInterfaces/interface_UserPattern_19114.htm).
