# Terraria 1.4.5.8 item image coverage

## Source contract and initial gap

`Live-yan/TerrariaDecompiledSource@8255d34616c780af12079425ac92a0a7aed87d71`, `Terraria.ID/ItemID.cs` blob `391d0ba08cb7a47bdd4456e48deca6c847ff0f69`, defines `ItemID.Count = 6196`: positive IDs are 1–6195. ID 0 is empty; nonstandard image 32135 remains untouched for compatibility.

Original main `d8b7a655e210fe377186a083635733ece85c3594` had 6086 PNG files but only 6084 positive in-range paths. There were **111 missing paths** (108 nondeprecated and 3 deprecated). None of the existing PNG containers was invalid. Exact missing IDs and the native texture-copy map are retained in `data/item-coverage-8255d346.json`. The original failed audit is Actions run 34552173003, artifact `item-coverage`.

## Final repairs: 112 changed PNGs

1. **62 missing texture aliases**: trapped chests 3665–3706 and 20 newer variants. Resolve native `ItemID.Sets.TextureCopyLoad` chains (including 3705 → 3665 → 48), then copy the exact canonical PNG bytes. No stored game ID is changed and no trap-sign UI overlay is baked into the thumbnail.
2. **49 images at 6147–6195**, including deprecated 6160, 6170 and 6171. These are exact nontransparent crops of the existing 40×40 UI atlas `PlayerWebsite@9e09f4e3aef37befc267aa51c190bea472726c8b/img/items.png`, Git blob `308b51c8089bc399cbf7dfab22c9c74bc30c952b`. Original rectangles, crop RGBA hashes and compressed input bytes are stored for offline reproduction.
3. **One existing incorrect alias, 5708**: the old image was 16×30 while native TextureCopyLoad requires 5697's 32×30 image. It is replaced by exact canonical bytes. All **67** native aliases are now checked byte-for-byte, not just the formerly missing 62.

All 6195 positive-ID PNG paths exist, decode and have visible pixels. The images total **2,138,114 bytes**. The 112 changed PNGs total **41,150 bytes**; relative to original main the net image increase is **40,829 bytes**. The complete manifest `index/items-1.4.5.8.json` records path, dimensions, bytes, SHA-256 and repair provenance for every image. Manifest SHA-256: `663b84f29c183bbd286e660eddf960ea640c90f36628bdde4eac8925201515c7`.

## Reproducible checks

```
python -m pip install Pillow==11.3.0
python scripts/item_coverage.py --check
python -m unittest discover -s scripts -p 'test_item_coverage.py' -v
python scripts/item_coverage.py --write
git diff --exit-code -- items index/items-1.4.5.8.json
```

The generator uses only committed crop bytes and existing canonical images. It verifies compressed input, offsets, dimensions, RGBA hashes, alias chains and all PNG decodes. Linux and Windows CI regenerate all 112 changes and compare the committed manifest. Temporary write workflows have been removed; the branch contains the real final assets.

## WLD / PLR integration and scope

WLD chest contents and PLR inventory/equipment share `items/item_{id}.png`. No codec or binary serialization change is required. Applications must advance their immutable **item** revision; merely merging CDN main does not change an old pinned URL. Mirrors must retain the same revision and cache keys must include it, preventing stale failed-cache entries from shadowing newly repaired images.

viewer-app PR #59 uses the complete item commit independently from CDN PR #3's player appearance version. Neither resource family removes or overwrites the other's paths. A user should not clear character/world/history data to update icons; resource-only cache cleanup is sufficient when needed, and missing cache files re-download automatically.

These are real UI thumbnails, not placeholders or invented art. The 49 atlas crops are not full-resolution original XNB exports. Except for the verified incorrect alias, existing artwork is retained. Source code establishes IDs and alias rules but cannot prove every historical pixel is identical to the current retail client; this PR provides complete ID coverage, not an unverified full artwork refresh. Modded/out-of-range IDs and uncached first use without network still need explicit fallback. WeChat GUI/device and game-client acceptance are separate from repository PNG and browser checks.
