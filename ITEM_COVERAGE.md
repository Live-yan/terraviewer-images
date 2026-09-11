# Terraria 1.4.5.8 item image coverage

## Verified source and initial gap

The ID contract is `Live-yan/TerrariaDecompiledSource@8255d34616c780af12079425ac92a0a7aed87d71`, `Terraria.ID/ItemID.cs` blob `391d0ba08cb7a47bdd4456e48deca6c847ff0f69`. `ItemID.Count = 6196`: the positive item range is 1–6195. ID 0 is empty; the pre-existing nonstandard image 32135 is retained for compatibility.

Original `main@d8b7a655e210fe377186a083635733ece85c3594` had 6086 PNGs but only 6084 positive in-range paths. The audit found 111 missing paths: 108 nondeprecated and 3 deprecated. None of the existing PNG containers was invalid. Full missing IDs are preserved in `data/item-coverage-8255d346.json`; the original failure report is the `item-coverage` artifact in Actions run 34552173003.

## Actual repairs

- 62 texture aliases: trapped chests 3665–3706 plus 20 newer variants. The game explicitly reuses textures through `ItemID.Sets.TextureCopyLoad`. The generator resolves chains (including 3705 → 3665 → 48) and copies the exact existing canonical PNG bytes. The in-game trap-sign overlay is not baked into these item thumbnails.
- 49 item images at 6147–6195, including deprecated IDs 6160, 6170 and 6171. These are exact nontransparent crops of the existing 40×40 UI atlas `PlayerWebsite@9e09f4e3aef37befc267aa51c190bea472726c8b/img/items.png`, verified Git blob `308b51c8089bc399cbf7dfab22c9c74bc30c952b`. The stored crop bytes, SHA-256 and original atlas rectangles are committed for reproducibility.

These are real UI thumbnails, not placeholders, guessed art or full-resolution original game XNB textures. Existing artwork is not blindly replaced. Source code determines IDs and alias rules, but cannot prove every pre-existing pixel matches the latest retail client. This PR closes ID coverage gaps; it does not claim a complete artwork refresh.

The repair adds 40,719 bytes of PNGs. All 6195 positive ID paths now exist, decode and contain visible pixels. The complete images total 2,138,004 bytes. Generated manifest `index/items-1.4.5.8.json` records every path, dimensions, byte length and SHA-256, plus repair provenance. Its SHA-256 is `261a5b883bbcb9adfabbde261144639d9a211b989d431a336fa6e8c665ea7847`.

## Reproducible validation

```
python -m pip install Pillow==11.3.0
python scripts/item_coverage.py --check
python -m unittest discover -s scripts -p 'test_item_coverage.py' -v
python scripts/item_coverage.py --write
git diff --exit-code -- items index/items-1.4.5.8.json
```

The generator is offline and only writes the 111 audited repairs plus the manifest. It validates its compressed input, byte offsets, dimensions, RGBA hash, native alias chains and all PNG decodes. Linux and Windows PR jobs independently repeat these checks. Real generated PNGs are committed: normal consumers do not run a temporary materialization workflow.

## WLD / PLR integration

World chest contents and player inventory/equipment share the exact `items/item_{id}.png` identity; no stored ID or binary codec changes are needed. Applications must update their pinned **item** asset revision, not merely merge this into main while keeping an old immutable URL. Every CDN mirror must retain that item revision, and the cache key must include it. Other asset families (for example PR #3 player appearance thumbnails) may keep their independent revision.

Application integration is tracked in viewer-app PR #59. The CDN repair itself works independently of PR #3 and does not remove any earlier public path. Modded/out-of-range IDs and offline first-time access to uncached images still require the application's explicit fallback; this coverage guarantee is for the pinned vanilla positive ID range.
