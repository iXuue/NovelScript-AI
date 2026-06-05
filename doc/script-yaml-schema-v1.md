# NovelScript AI 剧本 YAML Schema v1

## 1. 文档定位

本文定义 NovelScript AI 第一版用户可见剧本 YAML 的数据结构。

该 Schema 同时适用于：

- 右侧成果区展示的只读 YAML 预览。
- 用户最终导出的 YAML 文件。
- 用户可选导出的干净 JSON 文件。

用户导出 YAML 与用户干净 JSON 同构，只是序列化格式不同。

本文不定义内部剧本 JSON Schema。内部剧本 JSON 可以包含 `content_block_id`、`source_evidence_ids`、段落编号和 `traceability_index`；用户可见 YAML 不允许包含这些内部追溯字段。

## 2. 设计目标

1. 可读：用户看到的是剧本内容，不是系统调试信息。
2. 可校验：后端可以把 YAML 解析成普通对象后做 Schema Validator。
3. 可导出：同一份结构可以转换为 Markdown、DOCX、PDF、TXT 和干净 JSON。
4. 可追溯但不泄露：页面可以在 YAML 外侧展示来源证据按钮，但 YAML 正文不保存来源证据编号。
5. 可扩展：通过 `schema_version` 支持后续版本迁移。

## 3. 顶层结构

```yaml
schema_version: "1.0"
script:
  title: ""
  language: "zh-CN"
  format: "web_drama"
  genre: ""
  logline: ""
characters: []
scenes: []
```

顶层字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | string | 是 | Schema 版本，第一版固定为 `"1.0"`。 |
| `script` | object | 是 | 剧本整体信息。 |
| `characters` | array | 是 | 角色列表，可以为空数组。 |
| `scenes` | array | 是 | 场景列表，至少 1 场。 |

禁止出现的顶层字段：

- `content_block_id`
- `source_evidence_ids`
- `source_evidence_id`
- `chapter_id`
- `paragraph_id`
- `traceability_index`
- `run_id`
- `run_step_id`
- `prompt`
- `tool_calls`
- `developer_logs`

## 4. `script` Schema

```yaml
script:
  title: "雨夜归来"
  language: "zh-CN"
  format: "web_drama"
  genre: "suspense"
  logline: "多年后归来的女孩，在雨夜重新打开旧宅的门。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `title` | string | 是 | 剧本标题。 |
| `language` | string | 是 | 语言代码，默认 `zh-CN`。 |
| `format` | string | 是 | 剧本格式。 |
| `genre` | string | 否 | 类型，如 `suspense`、`romance`、`comedy`。 |
| `logline` | string | 否 | 一句话故事简介。 |

`format` 允许值：

```yaml
allowed_values:
  - short_drama
  - web_drama
  - film
  - tv_episode
  - stage_play
  - other
```

## 5. `characters` Schema

```yaml
characters:
  - name: "林雨"
    role: "protagonist"
    description: "多年后回到旧宅的年轻女性。"
    traits:
      - "克制"
      - "警觉"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 角色名。 |
| `role` | string | 否 | 角色功能，如主角、配角、反派。 |
| `description` | string | 否 | 角色简述。 |
| `traits` | array[string] | 否 | 性格或表演特征。 |

约束：

- `name` 在同一份剧本中应唯一。
- `traits` 只放用户可见的角色特征，不放内部分析过程。
- 不允许出现证据编号、段落编号或内部追溯 ID。

## 6. `scenes` Schema

```yaml
scenes:
  - scene_no: 1
    title: "雨夜归来"
    location: "旧宅门口"
    time_of_day: "night"
    summary: "林雨在雨夜回到旧宅，犹豫是否进门。"
    characters:
      - "林雨"
    dramatic_purpose: "建立人物回归和旧宅悬念。"
    beats:
      - "林雨站在旧宅门前。"
      - "她听见屋内传来轻响。"
      - "她推门进入。"
    content:
      - type: "action"
        text: "雨水顺着屋檐落下。林雨停在旧宅门前，手指悬在门环上。"
      - type: "dialogue"
        speaker: "林雨"
        text: "我回来了。"
      - type: "transition"
        text: "切至屋内。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `scene_no` | integer | 是 | 场景顺序，从 1 开始递增。 |
| `title` | string | 是 | 场景标题。 |
| `location` | string | 否 | 场景地点。 |
| `time_of_day` | string | 否 | 时间段。 |
| `summary` | string | 是 | 场景内容摘要。 |
| `characters` | array[string] | 是 | 本场出现角色名。 |
| `dramatic_purpose` | string | 否 | 本场在剧作结构中的功能。 |
| `beats` | array[string] | 否 | 本场关键节拍。 |
| `content` | array[object] | 是 | 本场剧本文本块，至少 1 个。 |

`time_of_day` 建议值：

```yaml
allowed_values:
  - morning
  - noon
  - afternoon
  - evening
  - night
  - dawn
  - unspecified
```

约束：

- `scenes` 至少包含 1 个场景。
- `scene_no` 必须从 1 开始连续递增。
- `characters` 中的角色名应能在顶层 `characters` 中找到；群众、路人等临时角色可以不登记。
- `content` 不允许为空。
- `scene_no` 不是内部追溯 ID，只是用户可见的场景顺序。

## 7. `content` 内容块 Schema

内容块用于表达具体剧本文本。

```yaml
content:
  - type: "action"
    text: "林雨抬头看向二楼的窗。"
  - type: "dialogue"
    speaker: "林雨"
    parenthetical: "压低声音"
    text: "谁在里面？"
  - type: "voice_over"
    speaker: "林雨"
    text: "我以为自己再也不会回来。"
```

字段说明：

| 字段 | 类型 | 必填 | 适用类型 | 说明 |
| --- | --- | --- | --- | --- |
| `type` | string | 是 | 全部 | 内容块类型。 |
| `text` | string | 是 | 全部 | 正文内容。 |
| `speaker` | string | 条件必填 | `dialogue`、`monologue`、`voice_over` | 说话角色。 |
| `parenthetical` | string | 否 | `dialogue`、`monologue`、`voice_over` | 表演提示，如“低声”。 |

`type` 允许值：

```yaml
allowed_values:
  - action
  - dialogue
  - monologue
  - voice_over
  - transition
```

类型规则：

- `action`：动作、环境、视觉描述。
- `dialogue`：角色对白，必须有 `speaker`。
- `monologue`：角色独白，必须有 `speaker`。
- `voice_over`：旁白或画外音，必须有 `speaker`。
- `transition`：转场提示，如“切至”“淡出”。

禁止字段：

- `content_block_id`
- `source_evidence_ids`
- `paragraph_id`
- `traceability`
- `confidence`
- `llm_reasoning`

## 8. 完整示例

```yaml
schema_version: "1.0"
script:
  title: "雨夜归来"
  language: "zh-CN"
  format: "web_drama"
  genre: "suspense"
  logline: "多年后归来的女孩，在雨夜重新打开旧宅的门。"
characters:
  - name: "林雨"
    role: "protagonist"
    description: "多年后回到旧宅的年轻女性。"
    traits:
      - "克制"
      - "警觉"
scenes:
  - scene_no: 1
    title: "雨夜归来"
    location: "旧宅门口"
    time_of_day: "night"
    summary: "林雨回到旧宅门前，听见屋内传来异常声响。"
    characters:
      - "林雨"
    dramatic_purpose: "建立人物回归和旧宅悬念。"
    beats:
      - "林雨站在旧宅门前。"
      - "屋内传来轻响。"
      - "林雨推门进入。"
    content:
      - type: "action"
        text: "雨水顺着屋檐落下。林雨停在旧宅门前，手指悬在门环上。"
      - type: "dialogue"
        speaker: "林雨"
        parenthetical: "低声"
        text: "我回来了。"
      - type: "transition"
        text: "切至屋内。"
```

## 9. Validator 规则

程序化 Schema Validator 至少检查：

1. YAML 可以被解析。
2. 顶层必须包含 `schema_version`、`script`、`characters`、`scenes`。
3. `schema_version` 必须为 `"1.0"`。
4. `script.title`、`script.language`、`script.format` 必填。
5. `scenes` 至少 1 个。
6. `scene_no` 从 1 开始连续递增。
7. 每个场景必须有 `title`、`summary`、`characters`、`content`。
8. 每个 `content` 块必须有合法 `type` 和非空 `text`。
9. `dialogue`、`monologue`、`voice_over` 必须有 `speaker`。
10. 不允许出现内部追溯字段，包括 `content_block_id`、`source_evidence_ids`、`paragraph_id`、`traceability_index`。
11. 页面来源证据按钮或证据标记不得写入 YAML 正文字段。

## 10. 与内部 JSON 的关系

内部 JSON 与用户 YAML 的区别：

| 项目 | 内部 JSON | 用户 YAML |
| --- | --- | --- |
| 是否是业务权威数据 | 是 | 否，只读预览和导出 |
| 是否包含 `content_block_id` | 是 | 否 |
| 是否包含来源证据 ID | 是 | 否 |
| 是否包含段落 ID | 是 | 否 |
| 是否包含 `traceability_index` | 单独保存并关联 | 否 |
| 是否可被用户直接编辑 | 否 | 否 |

转换规则：

1. 系统先生成并保存内部剧本 JSON。
2. 内部 JSON 经 Schema Validator 校验。
3. 系统移除内部追溯字段，生成干净对象。
4. 干净对象序列化为用户可见 YAML。
5. 页面如需展示来源证据按钮，通过内部 `content_block_id` 查询 `traceability_index`，但按钮和证据内容不进入 YAML。

## 11. 设计理由

### 11.1 为什么 YAML 不包含来源证据

来源证据是页面追溯能力，不是剧本文本本身。

如果把证据编号写进 YAML，会导致三个问题：

1. 用户导出的文件不够干净，像系统调试文件。
2. 后续 DOCX、PDF、TXT 转换时会混入不该出现的内部编号。
3. 一旦证据索引更新，导出的剧本文本会被内部追溯结构牵连。

因此，证据追溯保留在内部 JSON 和 `traceability_index`，用户 YAML 只承载剧本文本。

### 11.2 为什么保留 `schema_version`

第一版 Schema 不可能覆盖后续全部剧本格式。`schema_version` 可以让系统在未来新增字段或改变规则时做兼容处理，而不是让旧导出文件失去可解析性。

### 11.3 为什么把 `script`、`characters`、`scenes` 分开

这是剧本最稳定的三层结构：

- `script` 管整体元信息。
- `characters` 管角色表。
- `scenes` 管正文和场景顺序。

这样既适合右侧 YAML 预览，也适合后续导出成 Markdown、DOCX 和 PDF。

### 11.4 为什么 `content` 用块结构

剧本正文不是普通段落。动作、对白、独白、旁白、转场在展示和导出时格式不同。

使用内容块可以让系统：

- 对对白检查 `speaker`。
- 对动作和转场使用不同排版。
- 在内部 JSON 中用 `content_block_id` 追溯来源证据。
- 在用户 YAML 中删除内部 ID 后仍保持剧本文本结构清晰。

### 11.5 为什么不支持用户直接编辑 YAML

YAML 是内部 JSON 的只读投影。如果允许用户直接编辑 YAML，会带来同步问题：

- 内部 JSON、traceability_index 和 YAML 可能不一致。
- 用户修改可能破坏 Schema。
- 来源证据按钮无法可靠定位内容块。

因此用户修改必须通过对话提出，由系统生成新的内部 JSON 版本，再重新渲染 YAML。
