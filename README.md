# Luan 官方音效源 · Official sound source for Luan

[中文](#中文) · [English](#english)

## 中文

这里是 [Luan](https://luan.fuyo.app) 的官方音效源，提供 29 套程序合成的音效包，可以在 Luan 中直接试听和选用。全部音效都是 Luan 自己写程序合成的，没有使用录音或第三方素材。

### 在 Luan 中添加

1. 打开 Luan 设置的“音效”页，点“添加音效源”。
2. 粘贴下面的链接，确认添加：

   ```
   https://raw.githubusercontent.com/onepiece-studio/luan-sounds/main/luan.json
   ```

3. 下载完成后，在列表里选一套音效包。

添加和使用音效源需要 Luan Pro。音效包更新后，Luan 会提示你，确认后才会更新。

### 自建音效源

任何人都可以按同样的格式发布自己的音效源。格式、音频规则和校验工具见 [STANDARD.zh.md](STANDARD.zh.md)。

```sh
python3 tools/luan_repo.py build .   # 生成 luan.json 的 packs 数组
python3 tools/luan_repo.py check .   # 检查全部规则
```

### 许可

本仓库的音效文件（`packs/` 目录）仅限在 Luan 中使用，不得用于其他产品、不得再分发、不得商用。校验工具、JSON Schema 和文档使用 MIT 许可。详见 [LICENSE](LICENSE)。

## English

The official sound source for [Luan](https://luan.fuyo.app): 29 procedurally synthesized sound packs you can preview and use right inside Luan. Every sound was synthesized by code written for Luan; no recordings or third-party samples.

### Add it in Luan

1. Open Luan Settings → Sounds and click "Add Sound Source".
2. Paste this link and confirm:

   ```
   https://raw.githubusercontent.com/onepiece-studio/luan-sounds/main/luan.json
   ```

3. When the download finishes, pick a pack from the list.

Sound sources require Luan Pro. When packs are updated, Luan tells you and updates only after you confirm.

### Publish your own

Anyone can publish a sound source in the same format. See [STANDARD.md](STANDARD.md) for the manifest, the audio rules and the validator.

```sh
python3 tools/luan_repo.py build .   # generate the packs array of luan.json
python3 tools/luan_repo.py check .   # check every rule
```

### License

The sound files in `packs/` may only be used within Luan: not in other products, not redistributed, not for commercial use. The validator, JSON Schema and documentation are MIT licensed. See [LICENSE](LICENSE).
