# Luan Official Sound Source

The official sound source for [Luan](https://luan.fuyo.app): 29 procedurally synthesized sound packs you can preview and use right inside Luan. Every sound was synthesized by code written for Luan; no recordings or third-party samples.

## Add it in Luan

1. Open Luan Settings → Sounds and click "Add Sound Source".
2. Paste this link and confirm:

   ```
   https://raw.githubusercontent.com/onepiece-studio/luan-sounds/main/luan.json
   ```

3. When the download finishes, pick a pack from the list.

Sound sources require Luan Pro. When packs are updated, Luan tells you and updates only after you confirm.

## Publish your own

Anyone can publish a sound source in the same format. See [STANDARD.md](STANDARD.md) for the manifest, the audio rules and the validator.

```sh
python3 tools/luan_repo.py build .   # generate the packs array of luan.json
python3 tools/luan_repo.py check .   # check every rule
```

## License

The sound files in `packs/` may only be used within Luan: not in other products, not redistributed, not for commercial use. The validator, JSON Schema and documentation are MIT licensed. See [LICENSE](LICENSE).
