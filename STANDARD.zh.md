# Luan 音效仓库标准 v1

[English](STANDARD.md)

Luan 音效仓库是放在网上的一组静态文件：一份清单 `luan.json`，加上若干 WAV 文件。任何人都可以发布。Luan Pro 用户粘贴 `luan.json` 的地址即可添加，再从中选择音效包。在 Luan 界面中，这类仓库称为“**音效源**”。

本文面向仓库作者，规定清单格式、音频规则和托管要求。`tools/luan_repo.py`（只依赖 Python 3 标准库）负责生成清单，并检查下面的全部规则。

## 1. 两个版本号

| 版本号 | 位置 | 谁控制 | 含义 |
|---|---|---|---|
| `schemaVersion` | `luan.json` 顶层，整数 | Luan | 标准的结构版本。新增可选字段不升版本；只有不兼容的改动才加 1。v1 为 `1` |
| `version` | 每个音效包，整数 ≥ 1 | 仓库作者 | 包的内容版本。包内任何文件或元信息变化，都要加 1 |

清单的 `schemaVersion` 高于当前 Luan 支持的版本时，Luan 拒绝添加或更新，并提示用户更新 Luan。已经下载的内容继续可用。

仓库本身不设版本号：仓库名、描述的变化不需要用户确认；新增、移除了哪些包，对比前后两份清单就能得出。

## 2. 目录结构

```
<repo-root>/
├── luan.json                 # 清单。Luan 首先读取的唯一文件
├── packs/
│   └── <pack-id>/
│       ├── pack.json         # 作者手写：本包元信息
│       └── <event>.wav       # 1–9 个事件音效，文件名即事件名
├── README.md
└── LICENSE
```

- `luan.json` 的顶层字段由作者手写；`python3 tools/luan_repo.py build .` 扫描 `packs/*/pack.json` 和 WAV 文件，生成 `packs` 数组，并算出每个文件的 `sha256` 和 `size`。不要手写哈希。
- 标准只约束 `luan.json` 和音频文件。`pack.json` 和 `packs/` 目录布局是工具的约定：Luan 不读取 `pack.json`，只按 `luan.json` 中的 `file` 路径取文件。
- `pack.json` 写除 `id`（取目录名）和 `sounds`（自动生成）以外的包字段，例如 `{ "name": "夜雨", "version": 1, "license": "CC-BY-4.0" }`。

## 3. 清单 `luan.json`

```json
{
  "schemaVersion": 1,
  "id": "com.example.sounds",
  "name": "示例音效",
  "description": "写代码时用的轻柔音效",
  "author": { "name": "Example", "email": "hi@example.com", "url": "https://example.com" },
  "homepage": "https://github.com/example/luan-sounds",
  "packs": [
    {
      "id": "night-rain",
      "name": "夜雨",
      "description": "雨滴落在窗沿上的轻响",
      "version": 3,
      "license": "CC-BY-4.0",
      "author": { "name": "某位作者" },
      "sounds": {
        "session-start": { "file": "packs/night-rain/session-start.wav", "sha256": "<64 位小写十六进制>", "size": 96044 },
        "task-complete": { "file": "packs/night-rain/task-complete.wav", "sha256": "<64 位小写十六进制>", "size": 88120 }
      }
    }
  ]
}
```

| 字段 | 必填 | 规则 |
|---|---|---|
| `schemaVersion` | 是 | 整数，本版为 `1` |
| `id` | 是 | 1–128 字符，`^[a-z0-9]+([.-][a-z0-9]+)*$`，推荐反向域名。`builtin` 保留。同一地址永远不能改 |
| `name` | 是 | 1–64 字符，不含控制字符 |
| `description` | 否 | ≤ 280 字符 |
| `author` | 否 | `{ "name"（必填）, "email"?, "url"? }`；`url` 必须是 `https://` |
| `homepage` | 否 | `https://` 地址 |
| `packs` | 是 | 1–64 个，`id` 不重复 |
| `packs[].id` | 是 | 1–64 字符，`^[a-z0-9]+(-[a-z0-9]+)*$` |
| `packs[].name` | 是 | 1–64 字符，不含控制字符 |
| `packs[].description` | 否 | ≤ 280 字符 |
| `packs[].version` | 是 | 整数 ≥ 1 |
| `packs[].license` | 否 | SPDX 标识（如 `CC-BY-4.0`）或 `LicenseRef-…` |
| `packs[].author` | 否 | 与顶层 `author` 相同；缺省时沿用仓库作者 |
| `packs[].sounds` | 是 | 至少 1 个已知事件 |
| `sounds.<event>.file` | 是 | 相对路径，只允许 `A–Z a–z 0–9 . _ -` 和 `/`，≤ 255 字符；不允许空段、`.`、`..`；以小写 `.wav` 结尾 |
| `sounds.<event>.sha256` | 是 | 文件的 SHA-256，64 位小写十六进制 |
| `sounds.<event>.size` | 是 | 文件字节数，整数 |

长度按 Unicode 码位计算。整数必须写成 JSON 整数（`1`，不能写 `1.0` 或 `"1"`）。

### 事件

| 键 | 何时播放 |
|---|---|
| `session-start` | 会话开始 |
| `task-acknowledge` | 任务确认 |
| `task-complete` | 任务完成 |
| `task-error` | 任务出错 |
| `input-required` | 需要审批 |
| `input-required-question` | 需要回答问题 |
| `resource-limit` | 上下文压缩 |
| `user-spam` | 短时间内连续提交 |
| `idle-reminder` | 闲置提醒 |

一个包不必提供全部 9 个事件，缺少的事件使用 Luan 内置的默认音效。

### 向前兼容

- 不认识的字段：忽略。
- 不认识的事件键：忽略，不会导致整个仓库无效。以后新增事件不需要升 `schemaVersion`。
- 只有删除字段、改变已有字段的含义或类型这类不兼容改动，才升 `schemaVersion`。

`luan_repo.py check` 对不认识的字段和事件给出警告，方便发现拼写错误，但不算错误。

## 4. 音频规则

本标准、`luan_repo.py` 和 Luan 使用同一组数字。

| 规则 | 值 | `luan_repo.py` | Luan |
|---|---|---|---|
| 格式 | WAV，线性 PCM，16 / 24 位整数 | 报错 | 拒绝 |
| 采样率 | 44.1 kHz 或 48 kHz | 报错 | 拒绝 |
| 声道 | 1 或 2 | 报错 | 拒绝 |
| 时长 | 大于 0，最长 5 秒 | 报错 | 拒绝 |
| 单文件大小 | ≤ 2 MiB，并与 `size` 完全一致 | 报错 | 拒绝 |
| 仓库总大小 | 相同文件只算一次，合计 ≤ 64 MiB | 报错 | 拒绝 |
| 清单大小 | `luan.json` ≤ 1 MiB | 报错 | 拒绝 |
| 响度 | 推荐：峰值 ≤ −1 dBFS，响度接近 Luan 内置音效 | 警告 | 不拒绝，播放时压低 |

v1 只收 WAV，是因为 WAV 用标准库就能精确校验，不需要 ffmpeg，在 CI 和 App 里都一样。上限留有余量：5 秒、48 kHz、双声道、24 位的音频约 1.4 MiB。

Luan 会测量每个音效的峰值和 RMS，比同一事件的内置音效响时，就压低播放音量。Luan 只会调小，不会调大。

## 5. 托管要求

- 所有文件通过 HTTPS 原样返回内容。
- 所有文件必须与 `luan.json` 在同一主机、同一目录或其子目录下；跳转只在这个范围内跟随。
- GitHub raw 地址（`https://raw.githubusercontent.com/<owner>/<repo>/<branch>/luan.json`）和 GitHub Pages 满足要求。GitHub Releases 的附件会跳到其他主机，不满足。
- 多数主机的路径区分大小写。不要提交符号链接：GitHub raw 会把符号链接当成一个小文本文件返回。

## 6. 更新

Luan Pro 每 6 小时在后台检查一次已添加仓库的更新，用户也可以手动检查。有变化时显示摘要，例如“夜雨 v3 → v4 · 新增 2 套”，由用户决定是否更新。更新一次应用整份新清单。

发布包的改动：修改文件或元信息，把 `pack.json` 里的 `version` 加 1，运行 `build`，然后推送。Luan 对比前后清单的规则：

- 出现新的包 `id` 即新增，`id` 消失即移除。用户正在使用的包被移除时，Luan 回退到内置音效。
- 文件或元信息有变化的包，`version` 必须变大。内容变了而 `version` 没变或变小，Luan 视为无效清单，不提示更新。
- 仓库 `id` 不能变。

`luan_repo.py build` 发现包内容变了但版本没加时，会拒绝写入清单。`luan_repo.py check . --previous 旧的luan.json` 对照已发布的清单做同样的比较；示例 CI 工作流在每次推送和 PR 时都会这样检查。

## 7. 认证标记

Luan 内置一张很短的地址前缀名单，每条对应一个标记。仓库地址以名单中的前缀开头时，App 显示对应标记；官方仓库 `https://raw.githubusercontent.com/onepiece-studio/luan-sounds/` 显示“官方”。名单由 Luan 维护，只随新版 App 更新。

标记只说明“这个地址由谁控制”，不代表其他含义。清单里的 SHA-256 只保证下载到的文件就是清单列出的文件，不能证明发布者的身份。

## 8. 校验与发布

```sh
python3 tools/luan_repo.py build .   # 重新生成 packs 数组，然后检查
python3 tools/luan_repo.py check .   # 只检查；有错误时退出码为 1
```

每个问题输出为 `error: <位置>: <说明> [<规则>]`。警告（未知字段、峰值过高）不影响退出码。

要在 GitHub 上检查每次推送，把 `tools/luan_repo.py` 复制到自己的仓库，并从官方仓库 <https://github.com/onepiece-studio/luan-sounds> 复制 `.github/workflows/check.yml`。JSON Schema `schema/luan-v1.schema.json` 描述清单结构，供编辑器使用；哈希、大小、音频等其余规则由工具检查。

## 9. 音效许可

只发布你有权分发的音效，并写明使用条件：给每个包填写 `license`，并在仓库中附上 `LICENSE` 文件。
