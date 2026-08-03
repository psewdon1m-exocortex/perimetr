# Техническое задание

## Perimetr Agent Control Plane

**Версия документа:** 2.0
**Назначение:** управление множеством Agent Node внутри Perimetr
**Удалённый исполнитель:** `agent-node`
**Системный исполнитель на сервере:** Sindri
**Интерактивный shell:** отсутствует
**Режим наблюдения:** Live execution
**Test mode в панели:** отсутствует

---

# 1. Назначение модуля

**Perimetr Agent Control Plane** — часть системы Perimetr, отвечающая за регистрацию, размещение, наблюдение и управление Agent Node.

Модуль должен:

1. Управлять множеством Agent Node.
2. Привязывать Agent Node к различным блокам Perimetr.
3. Поддерживать общую библиотеку зарегистрированных агентов.
4. Принимать heartbeat от каждого агента.
5. Показывать доступность и состояние серверов.
6. Получать каталог команд Sindri.
7. Отправлять команды выбранному Agent Node.
8. Отображать выполнение в режиме Live execution.
9. Обрабатывать запросы approval.
10. Хранить историю заданий и аудит действий.
11. Сохранять данные агентов в резервных копиях Perimetr.
12. Восстанавливать связи с агентами после восстановления Perimetr.
13. Позволять удалить агента из интерфейса, не удаляя его с сервера.
14. Поддерживать отдельный защищённый механизм полного отзыва Agent Node.

---

# 2. Место Agent Control Plane в архитектуре

```text
Perimetr UI
    │
    ▼
Perimetr Agent Control Plane
    │
    │ HTTPS / mTLS
    ▼
Agent Node
    │
    │ JSON / NDJSON
    ▼
Sindri
    │
    ▼
Ubuntu Server
```

Браузер пользователя не подключается к Agent Node напрямую.

Все действия проходят через backend Perimetr.

---

# 3. Основные сущности Perimetr

Perimetr управляет следующими типами блоков:

```text
I as human in general
Laboratory
Perimetr
Projects
└── Subjects
Objects
```

## 3.1. I as human in general

Личный блок пользователя.

Не содержит панель управления Agent Node.

## 3.2. Laboratory

Блок лаборатории.

Может содержать:

```text
не более одного Agent Node
```

Предполагается, что Agent Node управляет основным рабочим сервером лаборатории.

## 3.3. Perimetr

Системный блок Perimetr.

Может содержать:

```text
не более одного Agent Node
```

Этот Agent Node относится к серверу, на котором размещена сама система Perimetr.

## 3.4. Subject

Subject находится внутри поля `Projects`.

Каждый Subject может:

```text
не иметь Agent Node;
иметь один Agent Node;
иметь несколько Agent Node.
```

Количество агентов Subject технически не ограничивается жёстко, но интерфейс и backend должны поддерживать пагинацию и работу с большим количеством записей.

## 3.5. Object

Object использует общий интерфейс блоков Perimetr, но не содержит панель Agent Node.

---

# 4. Общий интерфейс блоков

Блоки:

```text
Laboratory
Perimetr
Subject
Object
```

должны использовать тот же базовый интерфейс и визуальную систему, которые уже используются для блока:

```text
I as human in general
```

При реализации разработчик должен использовать существующие компоненты, правила компоновки и дизайн-систему Perimetr.

Полное описание интерфейса `I as human in general` не входит в данный документ, поскольку оно уже существует в основном проекте Perimetr.

---

# 5. Дополнительная панель Agent Node

Блоки:

```text
Laboratory
Perimetr
Subject
```

должны содержать дополнительную панель:

```text
Agent Nodes
```

Панель размещается ниже остальных панелей и элементов блока.

Блок `Object` такую панель не содержит.

---

# 6. Ограничения количества агентов

## Laboratory

```text
0 или 1 Agent Node
```

## Perimetr

```text
0 или 1 Agent Node
```

## Subject

```text
0 или несколько Agent Node
```

Если в Laboratory или Perimetr уже добавлен Agent Node, добавление второго должно быть заблокировано.

Интерфейс должен предложить:

```text
Open current Agent Node
Remove current Agent Node
Replace current Agent Node
```

Замена должна выполняться как две отдельные операции:

1. Удаление текущей привязки.
2. Добавление новой привязки.

---

# 7. Agent Registry и Agent Library

Необходимо разделять две сущности:

## 7.1. Agent Registry

Технический backend-реестр всех Agent Node, которые когда-либо были зарегистрированы или подключены к Perimetr.

Он хранит:

* Agent ID;
* endpoint;
* сертификат;
* fingerprint;
* состояние enrollment;
* heartbeat;
* историю;
* revocation;
* технические связи.

## 7.2. Agent Library

Пользовательская библиотека Agent Node, доступная в интерфейсе Perimetr.

В библиотеке отображаются только агенты, которые привязаны хотя бы к одному блоку.

---

# 8. Первое добавление Agent Node

Когда пользователь впервые добавляет новый Agent Node в любой поддерживаемый блок:

1. Выполняется enrollment.
2. Создаётся запись в Agent Registry.
3. Agent Node добавляется в Agent Library.
4. Создаётся привязка к текущему блоку.
5. Agent Node становится доступен для добавления в другие блоки.

Один Agent Node может быть одновременно привязан к нескольким блокам.

Пример:

```text
Agent Node: main-server

Assignments:
  Laboratory
  Subject: Project Alpha / Backend
  Subject: Project Beta / Infrastructure
```

При этом физически существует только один Agent Node и один управляемый сервер.

---

# 9. Добавление существующего агента

Кнопка `+` в панели Agent Nodes должна открывать библиотеку агентов.

Интерфейс добавления должен содержать:

```text
Search
Available Agent Nodes
Register new Agent Node
```

Для каждого агента в библиотеке показывать:

```text
Name
Status
Agent ID
Current assignments
```

Agent Node, уже привязанный к текущему блоку, нельзя добавить повторно.

---

# 10. Удаление агента из блока

Обычное удаление Agent Node из интерфейса означает только удаление привязки между Agent Node и текущим блоком.

Операция не должна:

* отправлять revoke;
* удалять `agent-node` с сервера;
* удалять Sindri;
* закрывать порт;
* удалять сертификаты;
* останавливать heartbeat;
* менять серверную инфраструктуру.

Кнопка в интерфейсе может называться:

```text
Delete
```

Но confirmation должен явно объяснять действие:

```text
Remove this Agent Node from the current Perimetr block?

The Agent Node and Sindri will remain installed on the server.
```

Кнопки:

```text
Remove
Cancel
```

---

# 11. Удаление последней привязки

Если Agent Node удаляется из последнего блока:

1. Он исчезает из пользовательской Agent Library.
2. Он больше не отображается в обычных блоках Perimetr.
3. Создание пользовательских jobs для него блокируется.
4. Backend сохраняет минимальную техническую запись.
5. Сертификат и identity не отзываются.
6. Agent Node не удаляется с сервера.
7. Heartbeat может продолжать приниматься в техническом режиме.

Техническое состояние:

```text
DETACHED
```

DETACHED Agent Node не должен отображаться в обычной библиотеке.

Backend должен сохранять его данные для:

* аудита;
* безопасности;
* восстановления из backup;
* предотвращения конфликтующего повторного enrollment;
* последующего revoke.

---

# 12. Очистка Agent Library

Agent Node удаляется из видимой Agent Library автоматически, если:

```text
assignment_count = 0
```

При этом техническая запись в Agent Registry сохраняется.

Полное физическое удаление записи из Agent Registry запрещено, если существуют:

* audit events;
* jobs;
* revocation records;
* certificate history;
* backup references.

---

# 13. Привязка Agent Node к блокам

Связь Agent Node и блока должна быть many-to-many.

Минимальная модель привязки:

```text
assignment_id
agent_id
block_id
block_type
position
created_at
created_by
```

Один Agent Node может иметь несколько assignments.

Один Subject может иметь несколько Agent Node.

---

# 14. Порядок Agent Node в блоке

В панели Agent Nodes записи идут вертикально сверху вниз.

Пользователь должен иметь возможность свободно менять порядок drag-and-drop.

Порядок сохраняется отдельно для каждого блока.

Пример:

```text
Subject A:
  1. Production
  2. Staging
  3. Build server

Subject B:
  1. Build server
  2. Production
```

Один и тот же Agent Node может иметь разную позицию в разных блоках.

---

# 15. Свёрнутый вид Agent Node

В обычном состоянии строка Agent Node показывает только:

```text
Name
Status
```

Пример:

```text
Production Server        ONLINE
Build Server             DEGRADED
Old Server               OFFLINE
```

Не следует перегружать свёрнутый список:

* IP-адресами;
* версиями;
* fingerprint;
* текущими ресурсами;
* списками команд.

Эта информация доступна после открытия Agent Node.

---

# 16. Статусы в свёрнутом списке

Поддерживаемые пользовательские статусы:

```text
ONLINE
BUSY
APPROVAL REQUIRED
DEGRADED
UNREACHABLE
OFFLINE
DETACHED
REVOKED
ERROR
```

Приоритет отображения:

```text
APPROVAL REQUIRED
ERROR
REVOKED
OFFLINE
UNREACHABLE
DEGRADED
BUSY
ONLINE
```

Если Agent Node выполняет job и одновременно требует approval, показывается:

```text
APPROVAL REQUIRED
```

---

# 17. Открытие Agent Node

Пользователь может развернуть запись Agent Node и перейти во внутренний интерфейс агента.

В открытом режиме интерфейс делится на две основные части:

```text
Left control column
Right Live execution area
```

---

# 18. Левая колонка Agent Node

Левая колонка состоит из двух зон.

## 18.1. Верхняя зона

Содержит:

* название Agent Node;
* текущий статус;
* Agent ID;
* heartbeat indicator;
* кнопку или блок `Settings`;
* кнопку возврата;
* кнопку удаления из текущего блока.

## 18.2. Нижняя зона

Содержит список доступных команд Sindri.

---

# 19. Правая часть Agent Node

Всю основную правую часть занимает:

```text
Live execution
```

Визуально она может быть оформлена как терминал или консольный поток.

При этом Live execution не является настоящим терминалом.

Пользователь не может:

* вводить shell-команды;
* передавать клавиатурный ввод на сервер;
* запускать произвольные процессы;
* получать PTY;
* вводить Linux username;
* вводить Linux password;
* вмешиваться напрямую в stdin Sindri.

---

# 20. Состояние Live execution без активного Job

Если job не выполняется, правая часть должна показывать:

```text
Agent Node name
Current state
Last heartbeat
Last completed job
Last job result
Waiting for a command
```

Пример:

```text
AGENT NODE · PRODUCTION SERVER

Status: ONLINE
Last heartbeat: 12 seconds ago
Last job: docker.info
Result: SUCCESS

Waiting for a command...
```

---

# 21. Live execution активного Job

Во время выполнения показывать:

* название Agent Node;
* action;
* пользователя, создавшего job;
* время начала;
* текущий статус;
* шаги;
* текущий шаг;
* длительность шагов;
* предупреждения;
* краткий stdout/stderr;
* approval events;
* итоговый результат.

Пример:

```text
SINDRI · SYSTEM / MAKE READY

✓ Checking operating system
✓ Checking available disk space
✓ Checking APT lock
→ Updating package index
– Installing packages
– Cleaning package cache
– Verifying result
```

---

# 22. События Live execution

Поддерживаемые события:

```text
job.created
job.dispatched
job.queued
job.started
step.started
step.completed
step.skipped
step.failed
job.input_required
job.approval_required
job.approved
job.rejected
job.cancel_requested
job.cancelled
job.completed
job.failed
connection.lost
connection.restored
```

Каждое событие должно иметь:

```text
event_id
sequence
agent_id
job_id
timestamp
type
status
message
```

---

# 23. Восстановление Live execution

При обновлении страницы или временном разрыве соединения интерфейс должен:

1. Получить сохранённые события job.
2. Восстановить правильный порядок по `sequence`.
3. Продолжить live stream с последнего события.
4. Не создавать визуальные дубликаты.
5. Не терять approval request.
6. Не создавать новый job.

---

# 24. Команды Agent Node

Список команд в левой нижней части формируется из Capability Catalog выбранного Agent Node.

Команды группируются:

```text
System
Firewall
Docker
Users
Certificates
Agent Node
```

Для каждой команды показывать:

* название;
* краткое описание;
* уровень риска;
* требуемые параметры;
* доступность.

---

# 25. Отсутствие test mode в панели

Perimetr не должен показывать:

```text
Run in test mode
Test command
Dry run
--test
```

Perimetr не должен отправлять пользователю тестовые версии команд.

Все jobs, созданные через панель, являются реальными операциями.

Поле:

```json
{
  "test": true
}
```

не должно присутствовать в публичном UI API Agent Control Plane.

Локальный `--test` Sindri остаётся доступен администратору непосредственно на сервере, но не через панель Perimetr.

---

# 26. Запуск команды

После выбора команды:

1. Perimetr строит форму по Capability Catalog.
2. Пользователь вводит параметры.
3. Backend повторно валидирует параметры.
4. Создаётся Job.
5. Job отправляется выбранному Agent Node.
6. Открывается Live execution.
7. Периметр отображает поступающие события.

Каждый job относится только к одному Agent Node.

Автоматическая массовая рассылка одной команды всем агентам не входит в текущий объём.

---

# 27. Approval request

Если Sindri определяет, что команда требует подтверждения, Agent Node отправляет в Perimetr:

```text
job.approval_required
```

Событие должно включать:

```text
Agent Node
Job ID
Command
Inputs
Risk
Warning
Plan
Plan hash
Approval ID
Expiration time
```

---

# 28. Глобальное approval-окно

При получении `approval_required` Perimetr должен немедленно открыть модальное окно в центре экрана.

Фон всей панели должен перейти в blur.

Окно располагается поверх текущего интерфейса независимо от того, какой блок открыт.

Пример:

```text
APPROVAL REQUIRED

Production Server requests permission to run:

system.reboot

The server will reboot and active connections will be interrupted.

Allow this command?

[No]     [Yes]
```

---

# 29. Содержимое approval-окна

Обязательно показывать:

* название Agent Node;
* блок или блоки, с которыми он связан;
* название команды;
* основные параметры;
* предупреждение;
* уровень риска;
* пользователя, запустившего команду;
* срок действия approval;
* кнопки `Yes` и `No`.

Подробный план может находиться в раскрываемом блоке:

```text
Show execution plan
```

---

# 30. Поведение approval-окна

Approval-окно нельзя подтвердить:

* кликом по фону;
* нажатием Enter по умолчанию;
* автоматическим timeout;
* повторным использованием предыдущего решения.

Кнопка `Yes` должна быть явным действием пользователя.

Кнопка `No` отклоняет выполнение.

Закрытие браузера или потеря сессии не означает approval.

Запрос остаётся в состоянии:

```text
APPROVAL_REQUIRED
```

до:

* approval;
* rejection;
* expiration.

---

# 31. Несколько approval requests

Если одновременно поступило несколько запросов approval:

1. Первый запрос показывается в модальном окне.
2. Остальные помещаются в очередь.
3. Интерфейс показывает количество:

```text
3 approval requests pending
```

4. После решения первого открывается следующий.
5. Каждый approval обрабатывается независимо.

Нельзя объединять approvals нескольких Agent Node в одно общее подтверждение.

---

# 32. Права на approval

Для подтверждения требуется право:

```text
agents.jobs.approve
```

Для отклонения требуется:

```text
agents.jobs.reject
```

Пользователь без права approval может видеть уведомление, но не получает активную кнопку `Yes`.

Все решения должны журналироваться.

---

# 33. Approval flow

```text
Sindri returns approval_required
→ Agent Node forwards approval request
→ Perimetr stores immutable request
→ global modal opens
→ authorized user selects Yes or No
→ Perimetr signs the decision
→ Agent Node receives the decision
→ Agent Node forwards it to Sindri
→ Sindri verifies plan hash
→ command executes or is cancelled
```

Perimetr не должен автоматически подтверждать ни одну команду.

---

# 34. Settings Agent Node

В верхней левой части открытого Agent Node должен находиться раскрываемый блок:

```text
Settings
```

Он показывает данные, использованные и полученные при регистрации:

```text
Display name
Agent ID
Domain
Port
Resolved IP
Enrollment date
Identity fingerprint
Certificate validity
Agent Node version
Sindri version
Sindri protocol version
Current assignments
Last heartbeat
```

Enrollment Token после завершения enrollment не показывается и не хранится в открытом виде.

---

# 35. Редактируемые настройки

Пользователь может менять:

```text
Display name
Tags
Environment
Notes
```

Нельзя свободно редактировать:

```text
Agent ID
Certificate fingerprint
Certificate serial
Controller identity
Enrollment state
```

Смена domain или port должна выполняться отдельной процедурой переподключения и проверки endpoint.

---

# 36. Кнопка удаления в Settings

В Settings должна находиться кнопка:

```text
Delete
```

В контексте открытого блока она означает:

```text
Remove Agent Node from this block
```

Перед удалением требуется отдельный confirmation:

```text
Remove "Production Server" from this block?

The Agent Node and Sindri will remain installed on the server.
```

Кнопки:

```text
Cancel
Remove
```

---

# 37. Удаление из последнего блока

Если это последняя привязка Agent Node, confirmation дополнительно показывает:

```text
This is the last Perimetr block using this Agent Node.

The Agent Node will also be removed from the visible Agent Library.
It will remain installed and enrolled on the server.
```

После подтверждения Agent Node переходит в техническое состояние:

```text
DETACHED
```

---

# 38. Отличие Delete от Revoke

Обычная кнопка `Delete`:

* удаляет только assignment;
* не удаляет Agent Node с сервера;
* не отзывает сертификат;
* не удаляет Sindri;
* не закрывает порт.

Операция:

```text
Revoke Agent Node
```

является отдельным административным действием.

Она должна находиться в отдельном разделе безопасности, а не использоваться обычной кнопкой Delete.

---

# 39. Agent Node Library

Библиотека должна поддерживать:

* поиск;
* фильтрацию;
* выбор агента;
* отображение assignments;
* добавление в текущий блок;
* регистрацию нового Agent Node.

Фильтры:

```text
Status
Environment
Tag
Assigned block type
Agent Node version
Sindri version
```

---

# 40. Global Agent Registry

Кроме библиотек внутри блоков, backend должен поддерживать глобальный реестр всех Agent Node.

Он необходим для:

* heartbeat;
* jobs;
* revoke;
* сертификатов;
* аудита;
* backup;
* восстановления;
* выявления дубликатов;
* обработки DETACHED Agent Node.

Глобальный технический реестр не обязан быть доступен обычному пользователю как отдельная страница.

Административный интерфейс может быть добавлен отдельно.

---

# 41. Работа с большим количеством Agent Node

Система должна поддерживать множество одновременно подключённых агентов.

Каждый Agent Node должен иметь независимые:

* heartbeat state;
* connection state;
* job queue;
* current job;
* approval requests;
* Live execution stream;
* capability catalog;
* certificate state;
* audit events.

Ошибка одного Agent Node не должна:

* блокировать остальные;
* останавливать heartbeat других нод;
* блокировать глобальную очередь jobs;
* повреждать Agent Library.

---

# 42. Ограничения параллельности

Для каждого Agent Node:

```text
Maximum mutating jobs: 1
Maximum read-only jobs: 4
Maximum queued jobs: 100
```

Ограничения применяются отдельно к каждому агенту.

Пример:

```text
Agent A: выполняет docker.install
Agent B: выполняет firewall.open
Agent C: выполняет info
```

Эти jobs могут идти одновременно.

---

# 43. Heartbeat

Perimetr должен принимать heartbeat каждого Agent Node каждые:

```text
30 seconds
```

Agent Node считается OFFLINE после:

```text
90 seconds
```

Heartbeat должен обновлять:

* состояние;
* last heartbeat;
* versions;
* hostname;
* uptime;
* boot ID;
* current job;
* queue length;
* CPU snapshot;
* RAM snapshot;
* disk snapshot;
* listener status.

---

# 44. Capability Catalog

Каждый Agent Node передаёт каталог доступных Sindri actions.

Perimetr должен хранить каталог отдельно для каждого агента.

Два Agent Node могут иметь разные:

* версии Sindri;
* команды;
* input schemas;
* уровни риска;
* возможности.

Интерфейс должен показывать только команды, реально доступные выбранному Agent Node.

---

# 45. Jobs

Каждый job содержит:

```text
job_id
request_id
agent_id
action
inputs
created_by
created_at
expires_at
status
```

Необходимо сохранять:

* requester;
* approver;
* canceller;
* plan;
* plan hash;
* события;
* result;
* error;
* log reference;
* версии Agent Node и Sindri.

---

# 46. Idempotency

При повторной отправке job должен использовать тот же:

```text
job_id
request_id
```

Perimetr не должен автоматически создавать новый request ID после сетевой ошибки.

Destructive-команда не должна повторяться из-за потери ответа.

---

# 47. Доступность Agent Node

Пользовательские состояния:

```text
ONLINE
BUSY
APPROVAL REQUIRED
DEGRADED
UNREACHABLE
OFFLINE
DETACHED
REVOKED
ERROR
```

Для OFFLINE, UNREACHABLE, REVOKED и ERROR запуск новых команд блокируется.

---

# 48. Резервное копирование

Данные Agent Control Plane должны входить в общую систему backup Perimetr.

Цель: после восстановления Perimetr не выполнять повторное ручное подключение каждого Agent Node.

---

# 49. Данные, входящие в backup

Backup должен включать:

## Agent Registry

* Agent ID;
* display name;
* domain;
* port;
* resolved IP;
* state;
* versions;
* metadata.

## Assignments

* связи Agent Node с блоками;
* тип блока;
* ID блока;
* порядок в списке;
* дата добавления;
* создатель связи.

## Certificates

* публичные identity-сертификаты;
* fingerprints;
* serial numbers;
* validity;
* certificate history;
* denylist.

## Controller identity

* Controller ID;
* Controller certificate;
* Controller private key.

Controller private key должен сохраняться только в зашифрованном виде.

## Jobs

* jobs;
* plans;
* approvals;
* results;
* Live execution events;
* errors.

## Agent metadata

* tags;
* environment;
* notes;
* capability catalogs;
* compatibility information.

## Security

* revocation records;
* denylist;
* audit log;
* permission-related history.

---

# 50. Данные, не входящие в обычный backup

Не должны сохраняться:

* private keys Agent Node;
* открытые Enrollment Tokens;
* пароли;
* secret Sindri inputs в открытом виде;
* временные nonce;
* истёкшие session credentials.

Приватный ключ Agent Node всегда остаётся только на управляемом сервере.

---

# 51. Controller identity и восстановление

Для восстановления связи без повторного enrollment необходимо восстановить ту же Controller identity.

Если Perimetr будет восстановлен с новым Controller certificate, Agent Node не будет доверять новой управляющей стороне.

Поэтому backup должен обязательно включать:

```text
Controller private key
Controller certificate
Controller ID
```

Controller private key должен:

* шифроваться отдельным backup key;
* иметь integrity check;
* не храниться как обычный JSON;
* не отображаться в UI;
* восстанавливаться до запуска Agent Control Plane.

---

# 52. Процесс восстановления из backup

После восстановления Perimetr:

1. Восстанавливается Controller identity.
2. Восстанавливается Agent Registry.
3. Восстанавливаются certificates и denylist.
4. Восстанавливаются assignments.
5. Восстанавливается порядок агентов в блоках.
6. Восстанавливается Agent Library.
7. Восстанавливаются jobs и audit.
8. Запускается heartbeat ingress.
9. Agent Node повторно подключаются с существующими identity.
10. Статусы обновляются после получения heartbeat.

Повторный enrollment не требуется.

---

# 53. Состояния после восстановления

Сразу после восстановления все Agent Node получают временное состояние:

```text
RESTORING
```

После heartbeat:

```text
RESTORING → ONLINE
RESTORING → DEGRADED
RESTORING → OFFLINE
```

Нельзя считать агента удалённым только потому, что heartbeat ещё не пришёл сразу после восстановления.

---

# 54. Проверка backup

Перед завершением backup необходимо проверить:

* структуру Agent Registry;
* references assignments;
* certificate fingerprints;
* Controller identity;
* denylist;
* database integrity;
* encryption metadata;
* backup version.

Backup без Controller identity должен считаться неполным для Agent Control Plane.

---

# 55. Восстановление UI

После restore пользователь должен увидеть:

* те же блоки;
* тех же Agent Node;
* те же assignments;
* тот же порядок;
* те же названия;
* те же tags;
* те же notes;
* ту же Agent Library.

Live execution для jobs, которые выполнялись во время происшествия, может перейти в:

```text
UNKNOWN
WAITING_RECONNECT
```

После reconnect Perimetr запрашивает фактическое состояние job.

---

# 56. Удаление Agent Node из Perimetr и backup

Обычное удаление assignment должно отражаться в новых backup.

При этом исторические backup могут содержать старую привязку.

Восстановление старого backup должно явно предупреждать:

```text
This backup contains Agent Node assignments that were later removed.
```

Восстановление должно быть управляемой операцией, а не автоматическим объединением старых и новых assignments.

---

# 57. Remote revoke

Remote revoke остаётся отдельной операцией.

Он:

* блокирует новые jobs;
* отзывает certificate;
* добавляет fingerprint в denylist;
* удаляет Agent Node с сервера;
* сохраняет Sindri и остальную инфраструктуру.

Для revoke требуется отдельное право:

```text
agents.revoke
```

Обычная кнопка Delete revoke не запускает.

---

# 58. Права пользователей

Минимальные permissions:

```text
agents.view
agents.assign
agents.unassign
agents.enroll
agents.settings.edit
agents.jobs.create
agents.jobs.cancel
agents.jobs.approve
agents.jobs.reject
agents.logs.view
agents.revoke
agents.force_revoke
```

## Назначение

`agents.assign` — добавить существующий Agent Node в блок.

`agents.unassign` — удалить Agent Node из блока.

`agents.enroll` — зарегистрировать новый Agent Node.

`agents.jobs.create` — отправлять команды.

`agents.jobs.approve` — подтверждать опасные команды.

---

# 59. Аудит

Необходимо журналировать:

```text
Agent Node enrolled
Agent Node assigned to block
Agent Node reordered
Agent Node removed from block
Agent Node detached
Agent Node settings changed
Job created
Job dispatched
Approval requested
Approval accepted
Approval rejected
Job cancelled
Job completed
Job failed
Agent Node revoked
Backup created
Agent data restored
```

Каждая запись содержит:

```text
timestamp
user
Agent ID
block ID
job ID
action
result
source session
```

Секретные данные в audit не записываются.

---

# 60. Data model

Минимальные таблицы или коллекции:

```text
agents
agent_assignments
agent_endpoints
agent_certificates
agent_capabilities
agent_heartbeats
agent_state_events
jobs
job_events
job_results
approval_requests
approval_decisions
revocation_records
certificate_denylist
audit_events
controller_identity
backup_manifests
```

---

# 61. Agent assignment model

```text
agent_assignments
├── id
├── agent_id
├── block_id
├── block_type
├── position
├── created_at
├── created_by
└── updated_at
```

Уникальное ограничение:

```text
agent_id + block_id
```

Один Agent Node нельзя дважды добавить в один блок.

---

# 62. Backend API для блоков

```text
GET    /api/blocks/<block-id>/agents
POST   /api/blocks/<block-id>/agents
DELETE /api/blocks/<block-id>/agents/<agent-id>
POST   /api/blocks/<block-id>/agents/reorder
```

Добавление существующего агента:

```json
{
  "agent_id": "..."
}
```

Изменение порядка:

```json
{
  "ordered_agent_ids": [
    "agent-1",
    "agent-3",
    "agent-2"
  ]
}
```

---

# 63. Backend API Agent Library

```text
GET  /api/agents/library
POST /api/agents/enroll
GET  /api/agents/<agent-id>
PATCH /api/agents/<agent-id>
```

Library endpoint должен возвращать только агентов:

```text
assignment_count > 0
```

DETACHED Agent Node в обычной library response не возвращаются.

---

# 64. Backend API jobs

```text
POST /api/agents/<agent-id>/jobs
GET  /api/agents/<agent-id>/jobs
GET  /api/agents/<agent-id>/jobs/<job-id>

POST /api/agents/<agent-id>/jobs/<job-id>/approve
POST /api/agents/<agent-id>/jobs/<job-id>/reject
POST /api/agents/<agent-id>/jobs/<job-id>/cancel

GET  /api/agents/<agent-id>/jobs/<job-id>/events
```

---

# 65. Approval API

Approve:

```text
POST /api/agents/<agent-id>/jobs/<job-id>/approve
```

Reject:

```text
POST /api/agents/<agent-id>/jobs/<job-id>/reject
```

Backend должен повторно проверить:

* user permission;
* approval ID;
* plan hash;
* expiration;
* Agent Node state;
* job state;
* replay.

---

# 66. Масштабирование

Система должна быть рассчитана на множество Agent Node.

Backend не должен создавать:

* отдельный process на каждый idle Agent Node;
* постоянный тяжёлый polling для каждого агента;
* отдельную неограниченную очередь в памяти;
* неограниченный Live execution buffer.

Рекомендуемая модель:

* heartbeat ingress;
* persistent job queue;
* connection pool;
* event stream service;
* stateless workers;
* shared persistent storage.

---

# 67. Ограничения

Рекомендуемые значения:

```text
Maximum pending jobs per Agent Node:        100
Maximum concurrent mutating jobs:             1
Maximum concurrent read-only jobs:            4
Maximum Live execution output per job:        1 MB
Maximum agents returned without pagination: 100
Maximum assignments per Subject page:        50
```

Большие списки должны использовать pagination или virtual scrolling.

---

# 68. Ошибки

Стабильные коды:

```text
AGENT_NOT_FOUND
AGENT_ALREADY_ASSIGNED
AGENT_LIMIT_REACHED
AGENT_DETACHED
AGENT_OFFLINE
AGENT_UNREACHABLE
AGENT_REVOKED
ASSIGNMENT_NOT_FOUND
INVALID_AGENT_ORDER
CAPABILITY_NOT_AVAILABLE
JOB_INVALID
JOB_DUPLICATE
JOB_EXPIRED
INPUT_REQUIRED
APPROVAL_REQUIRED
APPROVAL_EXPIRED
APPROVAL_REJECTED
APPROVAL_PLAN_CHANGED
CANCEL_NOT_SAFE
BACKUP_INCOMPLETE
CONTROLLER_IDENTITY_MISSING
RESTORE_CONFLICT
REVOCATION_FAILED
```

---

# 69. Тестирование интерфейса

Обязательные UI-тесты:

1. Agent Node panel отсутствует в Object.
2. Agent Node panel присутствует в Laboratory.
3. Agent Node panel присутствует в Perimetr.
4. Agent Node panel присутствует в Subject.
5. Laboratory не принимает второго агента.
6. Perimetr не принимает второго агента.
7. Subject принимает несколько агентов.
8. Drag-and-drop сохраняет порядок.
9. Один Agent Node добавляется в несколько блоков.
10. Удаление из одного блока не удаляет другие assignments.
11. Удаление последнего assignment очищает видимую library.
12. Открывается Agent Node interface.
13. Live execution занимает правую часть.
14. Команды находятся слева снизу.
15. Settings находятся слева сверху.
16. Delete не отправляет revoke.
17. Approval modal появляется по центру.
18. Фон переходит в blur.
19. Approval нельзя выполнить кликом по фону.
20. Несколько approvals обрабатываются последовательно.
21. В панели отсутствует test mode.
22. В интерфейсе отсутствует shell и PTY.

---

# 70. Backend-тестирование

Обязательные сценарии:

1. Регистрация множества Agent Node.
2. Одновременные heartbeat.
3. Независимые очереди jobs.
4. Параллельные jobs на разных Agent Node.
5. Один Agent Node с несколькими assignments.
6. DETACHED Agent Node.
7. Backup Agent Registry.
8. Backup Controller identity.
9. Полное восстановление.
10. Reconnect без enrollment.
11. Восстановление порядка assignments.
12. Восстановление Agent Library.
13. Approval после reconnect.
14. Job idempotency.
15. Remote revoke.
16. Force revoke.
17. Denylist после restore.

---

# 71. Критерии приёмки

Модуль считается готовым, если:

1. Поддерживает множество Agent Node.
2. Laboratory принимает максимум одного агента.
3. Perimetr принимает максимум одного агента.
4. Subject принимает несколько агентов.
5. Object не содержит Agent Node panel.
6. Agent Node panel размещена внизу блока.
7. Агенты отображаются вертикальным списком.
8. В свёрнутом виде видны только имя и статус.
9. Порядок меняется drag-and-drop.
10. Порядок сохраняется отдельно для каждого блока.
11. Кнопка `+` открывает Agent Library.
12. Можно зарегистрировать нового агента из любого подходящего блока.
13. Первый enrollment добавляет агента в library.
14. Агент можно добавить в другие блоки.
15. Последнее удаление очищает видимую library.
16. Backend сохраняет DETACHED record.
17. Delete не удаляет Agent Node с сервера.
18. Delete не удаляет Sindri.
19. Revoke является отдельной операцией.
20. В открытом Agent Node справа находится Live execution.
21. Слева сверху находятся status и Settings.
22. Слева снизу находится список команд.
23. Live execution не является терминалом.
24. Shell, PTY и Linux login отсутствуют.
25. Test mode отсутствует в панели.
26. Capability Catalog формирует доступные команды.
27. Approval открывается в центральном модальном окне.
28. Фон панели переходит в blur.
29. Approval содержит `Yes` и `No`.
30. Approval нельзя подтвердить неявно.
31. Несколько approvals образуют очередь.
32. Решения approval журналируются.
33. Каждый Agent Node имеет независимый heartbeat.
34. Каждый Agent Node имеет независимую очередь jobs.
35. Ошибка одного агента не блокирует остальные.
36. Agent Registry входит в backup.
37. Assignments входят в backup.
38. Порядок агентов входит в backup.
39. Certificates и fingerprints входят в backup.
40. Denylist входит в backup.
41. Controller identity входит в зашифрованный backup.
42. После restore повторный enrollment не требуется.
43. После restore восстанавливается интерфейс блоков.
44. После restore Agent Node автоматически возвращаются ONLINE после heartbeat.
45. Private keys Agent Node не хранятся в Perimetr.
46. Enrollment Tokens не сохраняются после enrollment.
47. Есть unit, integration, UI и end-to-end tests.
48. Реализация использует существующую дизайн-систему Perimetr.

---

# 72. Итоговый пользовательский сценарий

```text
User opens Laboratory, Perimetr or Subject
→ sees Agent Nodes panel at the bottom
→ clicks +
→ selects Agent Node from library or registers a new one
→ Agent Node appears in the vertical list
→ user reorders agents by drag-and-drop
→ user opens an Agent Node
→ left side shows status, settings and commands
→ right side shows Live execution
→ user selects a Sindri command
→ Perimetr sends the job
→ Live execution displays progress
→ dangerous command produces a global approval modal
→ the background becomes blurred
→ user selects Yes or No
→ the decision is sent to Agent Node
→ Sindri completes or cancels the operation
→ Perimetr stores the result and audit
```

---

# 73. Итоговый сценарий backup и восстановления

```text
Perimetr creates a backup
→ saves Controller identity
→ saves Agent Registry
→ saves certificates and denylist
→ saves assignments and ordering
→ saves Agent Library metadata
→ saves jobs, approvals and audit

Incident occurs
→ Perimetr is restored from backup
→ the same Controller identity is restored
→ Agent Registry and assignments are restored
→ blocks display the same Agent Nodes in the same order
→ heartbeat ingress starts
→ existing Agent Node reconnect
→ statuses are updated
→ no repeated manual enrollment is required
```
