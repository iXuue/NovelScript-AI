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
6. 可安全解析：禁止依赖 YAML 自定义 tag、复杂 alias 或执行型解析能力。

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

v1 扩展策略：

- v1 不允许任意扩展字段。
- 任何新增字段都必须先更新本文档和 Validator，再进入生成链路。
- 如果新增字段会改变导出语义，应升级 `schema_version`。
- 生成器不得输出本文档未定义的字段。

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
- `summary` 是用户可见的场景概述，属于 YAML 内容。
- `dramatic_purpose` 和 `beats` 是用户可见的工作稿字段，不是内部追溯字段；如果导出模板只需要纯剧本文本，导出层可以不展示它们，但不得修改 YAML/干净 JSON 的字段语义。

## 7. 字符串、空值和换行规则

### 7.1 空值规则

- 必填字段不得为空字符串。
- 可选字段没有内容时应省略，不写 `null`。
- 数组字段如果必填但暂无内容，允许使用空数组的只有 `characters`；`scenes` 和 `content` 不允许为空数组。
- 生成器不得输出字符串 `"null"`、`"N/A"`、`"无"` 来伪装缺失值。

### 7.2 字符串规则

- 字符串首尾空白应在生成或导出前 trim。
- `script.title` 建议不超过 80 个中文字符。
- `scene.title` 建议不超过 60 个中文字符。
- 单个 `content.text` 建议不超过 800 个中文字符；超长动作或对白应拆成多个内容块。
- `parenthetical` 建议不超过 30 个中文字符。

### 7.3 多行规则

`text` 允许多行。多行文本应使用 YAML literal block：

```yaml
text: |
  她站在门口。
  屋内没有灯，只有钟声。
```

多行规则：

- 多行 `text` 仍然是一个内容块。
- 不允许在同一个 `text` 中混写多个说话人的对白。
- 如果出现多轮对白，应拆成多个 `dialogue` 内容块。

## 8. `content` 内容块 Schema

内容块用于表达具体剧本文本。

```yaml
content:
  - type: "action"
    text: "林雨抬头看向二楼的窗。"
  - type: "dialogue"
    speaker: "林雨"
    parenthetical: "压低声音"
    text: "谁在里面？"
  - type: "narration"
    text: "雨声吞没了她的脚步。"
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
  - narration
  - voice_over
  - transition
```

类型规则：

- `action`：动作、环境、视觉描述。
- `dialogue`：角色对白，必须有 `speaker`。
- `monologue`：角色独白，必须有 `speaker`。
- `voice_over`：角色画外音，必须有 `speaker`。
- `narration`：非角色旁白，不要求 `speaker`。
- `transition`：转场提示，如“切至”“淡出”。

说话者规则：

- `dialogue`、`monologue`、`voice_over` 的 `speaker` 必须是顶层 `characters.name` 中的角色名。
- 如果需要非角色旁白，使用 `narration`，不要把 `speaker` 写成内部标记。
- 如果项目确实需要固定旁白角色，应把该角色加入 `characters`，再使用 `voice_over`。

禁止字段：

- `content_block_id`
- `source_evidence_ids`
- `paragraph_id`
- `traceability`
- `confidence`
- `llm_reasoning`

## 9. YAML 安全解析和页面追溯定位

### 9.1 YAML 安全解析规则

系统解析 YAML 时必须使用安全解析策略：

- 只允许标准 YAML 标量、对象和数组。
- 禁止自定义 tag，例如 `!!python/object`。
- 禁止执行型构造、外部引用或运行时代码。
- 不依赖 anchor / alias 表达业务语义。
- 如果解析器检测到重复 key，应判定为非法 YAML。
- YAML 解析后必须再执行 Schema Validator，不能只检查能否解析。

### 9.2 页面追溯定位规则

用户 YAML 不包含 `content_block_id`。页面需要展示来源证据按钮时，不应把追溯字段写入 YAML，而应使用系统内部的 UI 侧映射。

推荐内部映射结构：

```yaml
ui_trace_overlay:
  - yaml_pointer: "/scenes/0/content/1"
    content_block_id: "CB001"
    source_evidence_ids:
      - "EV001"
```

规则：

- `ui_trace_overlay` 不属于用户 YAML Schema。
- `ui_trace_overlay` 不进入用户导出文件。
- `yaml_pointer` 使用 YAML 解析后的 JSON Pointer 路径。
- 页面根据 `yaml_pointer` 找到对应内容块，再展示来源证据按钮。
- 用户点击按钮后，系统通过 `content_block_id` 查询 `traceability_index`。
- 如果用户通过对话修改剧本，系统必须重新生成内部 JSON、YAML 和 `ui_trace_overlay`。

这样可以同时满足两个要求：

- 用户 YAML 保持干净。
- 页面仍然能围绕具体内容块展示来源证据。

## 10. 完整示例

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
      - type: "narration"
        text: "多年未启的旧宅，像是在等她。"
      - type: "transition"
        text: "切至屋内。"
```

## 11. Validator 规则

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
12. v1 不允许未定义字段。
13. `characters.name` 应唯一。
14. `dialogue`、`monologue`、`voice_over` 的 `speaker` 必须能在 `characters.name` 中找到。
15. `action`、`transition`、`narration` 不应包含 `speaker`。

## 12. 可执行 JSON Schema

YAML 解析后应按下面的 JSON Schema 校验。该 Schema 负责结构校验；跨字段规则如 `scene_no` 连续、角色名唯一、`speaker` 是否存在于人物表，需要由程序化 Validator 额外检查。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://novelscript.ai/schemas/script-yaml-v1.schema.json",
  "title": "NovelScript AI User Script YAML Schema v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "script", "characters", "scenes"],
  "properties": {
    "schema_version": {
      "const": "1.0"
    },
    "script": {
      "$ref": "#/$defs/script"
    },
    "characters": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/character"
      }
    },
    "scenes": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "#/$defs/scene"
      }
    }
  },
  "$defs": {
    "nonEmptyString": {
      "type": "string",
      "minLength": 1
    },
    "shortString": {
      "type": "string",
      "minLength": 1,
      "maxLength": 120
    },
    "script": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "language", "format"],
      "properties": {
        "title": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        },
        "language": {
          "type": "string",
          "minLength": 1
        },
        "format": {
          "type": "string",
          "enum": ["short_drama", "web_drama", "film", "tv_episode", "stage_play", "other"]
        },
        "genre": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        },
        "logline": {
          "type": "string",
          "minLength": 1,
          "maxLength": 300
        }
      }
    },
    "character": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name"],
      "properties": {
        "name": {
          "type": "string",
          "minLength": 1,
          "maxLength": 60
        },
        "role": {
          "type": "string",
          "minLength": 1,
          "maxLength": 80
        },
        "description": {
          "type": "string",
          "minLength": 1,
          "maxLength": 500
        },
        "traits": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80
          },
          "uniqueItems": true
        }
      }
    },
    "scene": {
      "type": "object",
      "additionalProperties": false,
      "required": ["scene_no", "title", "summary", "characters", "content"],
      "properties": {
        "scene_no": {
          "type": "integer",
          "minimum": 1
        },
        "title": {
          "type": "string",
          "minLength": 1,
          "maxLength": 60
        },
        "location": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "time_of_day": {
          "type": "string",
          "enum": ["morning", "noon", "afternoon", "evening", "night", "dawn", "unspecified"]
        },
        "summary": {
          "type": "string",
          "minLength": 1,
          "maxLength": 500
        },
        "characters": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/nonEmptyString"
          },
          "uniqueItems": true
        },
        "dramatic_purpose": {
          "type": "string",
          "minLength": 1,
          "maxLength": 500
        },
        "beats": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200
          }
        },
        "content": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/contentBlock"
          }
        }
      }
    },
    "contentBlock": {
      "oneOf": [
        {
          "$ref": "#/$defs/actionBlock"
        },
        {
          "$ref": "#/$defs/dialogueBlock"
        },
        {
          "$ref": "#/$defs/monologueBlock"
        },
        {
          "$ref": "#/$defs/voiceOverBlock"
        },
        {
          "$ref": "#/$defs/narrationBlock"
        },
        {
          "$ref": "#/$defs/transitionBlock"
        }
      ]
    },
    "actionBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "text"],
      "properties": {
        "type": {
          "const": "action"
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 800
        }
      }
    },
    "dialogueBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "speaker", "text"],
      "properties": {
        "type": {
          "const": "dialogue"
        },
        "speaker": {
          "$ref": "#/$defs/shortString"
        },
        "parenthetical": {
          "type": "string",
          "minLength": 1,
          "maxLength": 30
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 800
        }
      }
    },
    "monologueBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "speaker", "text"],
      "properties": {
        "type": {
          "const": "monologue"
        },
        "speaker": {
          "$ref": "#/$defs/shortString"
        },
        "parenthetical": {
          "type": "string",
          "minLength": 1,
          "maxLength": 30
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 800
        }
      }
    },
    "voiceOverBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "speaker", "text"],
      "properties": {
        "type": {
          "const": "voice_over"
        },
        "speaker": {
          "$ref": "#/$defs/shortString"
        },
        "parenthetical": {
          "type": "string",
          "minLength": 1,
          "maxLength": 30
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 800
        }
      }
    },
    "narrationBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "text"],
      "properties": {
        "type": {
          "const": "narration"
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 800
        }
      }
    },
    "transitionBlock": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "text"],
      "properties": {
        "type": {
          "const": "transition"
        },
        "text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        }
      }
    }
  }
}
```

## 13. 与内部 JSON 的关系

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

## 14. 设计理由

### 14.1 为什么 YAML 不包含来源证据

来源证据是页面追溯能力，不是剧本文本本身。

如果把证据编号写进 YAML，会导致三个问题：

1. 用户导出的文件不够干净，像系统调试文件。
2. 后续 DOCX、PDF、TXT 转换时会混入不该出现的内部编号。
3. 一旦证据索引更新，导出的剧本文本会被内部追溯结构牵连。

因此，证据追溯保留在内部 JSON 和 `traceability_index`，用户 YAML 只承载剧本文本。

### 14.2 为什么保留 `schema_version`

第一版 Schema 不可能覆盖后续全部剧本格式。`schema_version` 可以让系统在未来新增字段或改变规则时做兼容处理，而不是让旧导出文件失去可解析性。

### 14.3 为什么把 `script`、`characters`、`scenes` 分开

这是剧本最稳定的三层结构：

- `script` 管整体元信息。
- `characters` 管角色表。
- `scenes` 管正文和场景顺序。

这样既适合右侧 YAML 预览，也适合后续导出成 Markdown、DOCX 和 PDF。

### 14.4 为什么 `content` 用块结构

剧本正文不是普通段落。动作、对白、独白、旁白、转场在展示和导出时格式不同。

使用内容块可以让系统：

- 对对白检查 `speaker`。
- 对动作和转场使用不同排版。
- 在内部 JSON 中用 `content_block_id` 追溯来源证据。
- 在用户 YAML 中删除内部 ID 后仍保持剧本文本结构清晰。

### 14.5 为什么不支持用户直接编辑 YAML

YAML 是内部 JSON 的只读投影。如果允许用户直接编辑 YAML，会带来同步问题：

- 内部 JSON、traceability_index 和 YAML 可能不一致。
- 用户修改可能破坏 Schema。
- 来源证据按钮无法可靠定位内容块。

因此用户修改必须通过对话提出，由系统生成新的内部 JSON 版本，再重新渲染 YAML。

### 14.6 为什么不用 `block_no` 做追溯定位

`block_no` 虽然不是内部 ID，但它仍然会进入用户可见 YAML。这样会把页面交互需要和剧本文本结构绑定在一起。

第一版采用内部 `ui_trace_overlay`，原因是：

- YAML 正文保持纯净。
- 导出文件不出现为了页面按钮服务的字段。
- 页面仍可通过 `yaml_pointer` 把证据按钮挂到具体内容块旁边。
- 用户通过对话修改剧本后，系统可以重新生成 overlay，而不是要求用户维护编号。
