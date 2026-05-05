#!/usr/bin/env python3
"""
Generate CDN-ready JSON files for terraviewer mini program from Tdecoder metadata output.

Reads:
  - Tdecoder artifacts: bestiary.generated.json, tile_ids.generated.json, wall_ids.generated.json, runtime_assets.generated.json
  - Terraria localization: zh-Hans/Items.json, en-US/Items.json

Outputs (to CDN repo index/ and pixel/ directories):
  - index/bestiary.json        (compact format for mini program)
  - index/chest_items.json     (compact format for mini program)
  - pixel/game_data.json       (tile/wall/paint names + base colors)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List

# --- Paths ---
# Auto-detect WSL vs Windows paths
import platform
_is_wsl = "microsoft" in platform.uname().release.lower() if hasattr(platform.uname(), 'release') else False

if _is_wsl:
    TDECODER_ARTIFACTS = Path("/mnt/c/Users/depths/Desktop/Tdecoder/TerrariaServerHook/artifacts/metadata/latest")
    CDN_REPO = Path("/mnt/d/Code/CLionProjects/terraviewer-images")
    CODE_DIR = Path("/mnt/c/Users/depths/Desktop/Tdecoder/code")
else:
    TDECODER_ARTIFACTS = Path(r"C:\Users\depths\Desktop\Tdecoder\TerrariaServerHook\artifacts\metadata\latest")
    CDN_REPO = Path(r"D:\Code\CLionProjects\terraviewer-images")
    CODE_DIR = Path(r"C:\Users\depths\Desktop\Tdecoder\code")

ZH_ITEMS_FILE = CODE_DIR / "Terraria.Localization.Content.zh-Hans.Items.json"
EN_ITEMS_FILE = CODE_DIR / "Terraria.Localization.Content.en-US.Items.json"


def load_json(path: Path):
    """Load JSON with UTF-8 BOM handling."""
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def derive_npc_type(entry):
    """
    Derive NPC type from unlockProvider and unlockRequirements.
    Matches TerrariaServerHook's DeriveNpcType + DeriveNpcTypeFromComposite logic.
    Returns: "enemy", "critter", or "town"
    """
    unlock_provider = entry.get("unlockProvider")
    if not unlock_provider:
        return "enemy"

    mapping = {
        "CommonEnemyUICollectionInfoProvider": "enemy",
        "CritterUICollectionInfoProvider": "critter",
        "TownNPCUICollectionInfoProvider": "town",
        "GoldCritterUICollectionInfoProvider": "critter",
        "SalamanderShellyDadUICollectionInfoProvider": "enemy",
    }

    if unlock_provider in mapping:
        return mapping[unlock_provider]

    if unlock_provider == "HighestOfMultipleUICollectionInfoProvider":
        # Composite provider - NPCs with multiple bestiary entries (body parts, linked NPCs)
        # Tdecoder's DeriveNpcTypeFromComposite examines child provider TYPES at runtime.
        # Since we can't access runtime objects, use NPC ID lookup for known composites.
        npc_id = entry.get("npcNetId", 0)
        # Known composite NPC classifications (verified against Terraria source):
        # - Bosses with linked town NPCs: type = enemy (the boss is the primary)
        # - Critters with variants: type = critter
        # - Town NPCs with transformations: type = town
        COMPOSITE_TYPE_OVERRIDE = {
            35: "enemy",    # SkeletronHead (boss, linked to Clothier)
            37: "town",     # OldMan (town NPC)
            68: "enemy",    # DungeonGuardian (enemy, linked to Clothier)
            362: "critter", # Duck (critter)
            364: "critter", # DuckWhite (critter)
            534: "town",    # DemonTaxCollector → TaxCollector (town NPC)
            602: "critter", # Seagull (critter)
            608: "critter", # Grebe (critter)
        }
        if npc_id in COMPOSITE_TYPE_OVERRIDE:
            return COMPOSITE_TYPE_OVERRIDE[npc_id]
        # Fallback: examine unlock requirements
        reqs = entry.get("unlockRequirements", [])
        trackers = {r.get("tracker", "") for r in reqs}
        if "Kills" in trackers:
            return "enemy"
        if "Sights" in trackers:
            return "critter"
        return "enemy"

    return "enemy"


def build_bestiary_compact(bestiary_data):
    """
    Convert bestiary.generated.json to compact CDN format.
    Output: [{id, c, z, t}, ...]
    """
    entries = bestiary_data["entries"]
    result = []
    for entry in entries:
        npc_type = derive_npc_type(entry)
        result.append({
            "id": entry["npcNetId"],
            "c": entry["bestiaryCreditId"],
            "z": entry["name_zh"],
            "t": npc_type,
        })
    result.sort(key=lambda x: x["id"])
    return result


def build_game_data(tile_ids_data, wall_ids_data, runtime_assets):
    """
    Build game_data.json from Tdecoder metadata.
    Merges with existing CDN data to fill in missing names.
    Contains: itemNames (Tiles/Walls/Paints), baseColors (tiles/walls/paints)
    """
    # Load existing CDN game_data for fallback names
    existing_game_data_path = CDN_REPO / "pixel" / "game_data.json"
    existing = {}
    if existing_game_data_path.exists():
        with open(existing_game_data_path, encoding="utf-8") as f:
            existing = json.load(f)

    existing_tile_names = existing.get("itemNames", {}).get("Tiles", {})
    existing_wall_names = existing.get("itemNames", {}).get("Walls", {})

    # --- Tile names and colors ---
    tile_names = {}
    tile_colors = {}
    for tile in tile_ids_data["tiles"]:
        tid = str(tile["id"])
        name = tile.get("name_zh") or existing_tile_names.get(tid)
        if name:
            tile_names[tid] = name
        if tile.get("hex"):
            tile_colors[tid] = tile["hex"]

    # --- Wall names and colors ---
    wall_names = {}
    wall_colors = {}
    for wall in wall_ids_data["walls"]:
        wid = str(wall["id"])
        name = wall.get("name_zh") or existing_wall_names.get(wid)
        if name:
            wall_names[wid] = name
        if wall.get("hex"):
            wall_colors[wid] = wall["hex"]

    # --- Paint names (from Terraria PaintID enum + localization) ---
    paint_names = build_paint_names()

    return {
        "itemNames": {
            "Tiles": tile_names,
            "Walls": wall_names,
            "Paints": paint_names,
        },
        "baseColors": {
            "tiles": tile_colors,
            "walls": wall_colors,
        },
    }


def build_paint_names():
    """
    Build paint ID -> Chinese name mapping from Terraria's localization.
    Paint IDs are defined in Terraria.PaintID enum.
    """
    # Hardcoded from Terraria source + zh-Hans localization
    # These are the 31 paint types in Terraria 1.4.4+
    paint_map = {
        "1": "红漆",
        "2": "橙漆",
        "3": "黄漆",
        "4": "橙绿漆",
        "5": "绿漆",
        "6": "青绿漆",
        "7": "青漆",
        "8": "天蓝漆",
        "9": "蓝漆",
        "10": "紫漆",
        "11": "蓝紫漆",
        "12": "粉漆",
        "13": "深红漆",
        "14": "深橙漆",
        "15": "深黄漆",
        "16": "深橙绿漆",
        "17": "深绿漆",
        "18": "深青绿漆",
        "19": "深青漆",
        "20": "深天蓝漆",
        "21": "深蓝漆",
        "22": "深紫漆",
        "23": "深蓝紫漆",
        "24": "深粉漆",
        "25": "黑漆",
        "26": "白漆",
        "27": "灰漆",
        "28": "棕漆",
        "29": "暗影漆",
        "30": "反色漆",
        "31": "夜明涂料",
        "32": "回声涂料",
    }
    return paint_map


def build_chest_items_compact(chest_items_data):
    """
    Convert chest_items.generated.json to compact CDN format.
    Input:  {items: [{itemId, internalName, name_en, name_zh}], prefixes: [{prefixId, ...}]}
    Output: {items: [{id, z}], prefixes: [{id, z}]}
    """
    items = [{"id": item["itemId"], "z": item["name_zh"]} for item in chest_items_data["items"]]
    prefixes = [{"id": p["prefixId"], "z": p["name_zh"]} for p in chest_items_data["prefixes"]]
    return {"items": items, "prefixes": prefixes}


def main():
    print("=" * 60)
    print("CDN File Generator for Terraviewer")
    print("=" * 60)

    # --- 1. Generate bestiary.json ---
    bestiary_src = TDECODER_ARTIFACTS / "bestiary.generated.json"
    if bestiary_src.exists():
        print(f"\n[1/3] Generating bestiary.json from {bestiary_src}")
        bestiary_data = load_json(bestiary_src)
        bestiary_compact = build_bestiary_compact(bestiary_data)
        out_path = CDN_REPO / "index" / "bestiary.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(bestiary_compact, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  -> {out_path} ({len(bestiary_compact)} entries)")

        # Verify NPC types
        type_counts = {}
        for entry in bestiary_compact:
            t = entry["t"]
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"  NPC types: {type_counts}")
    else:
        print(f"\n[1/3] SKIPPED bestiary.json - {bestiary_src} not found")

    # --- 2. Generate chest_items.json ---
    chest_src = TDECODER_ARTIFACTS / "chest_items.generated.json"
    if chest_src.exists():
        print(f"\n[2/3] Generating chest_items.json from {chest_src}")
        chest_data = load_json(chest_src)
        chest_compact = build_chest_items_compact(chest_data)
        out_path = CDN_REPO / "index" / "chest_items.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chest_compact, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  -> {out_path} ({len(chest_compact['items'])} items, {len(chest_compact['prefixes'])} prefixes)")
    else:
        print(f"\n[2/3] SKIPPED chest_items.json - {chest_src} not found")
        print("  NOTE: Run Tdecoder with latest build to generate chest_items.generated.json")

    # --- 3. Generate game_data.json ---
    tile_src = TDECODER_ARTIFACTS / "tile_ids.generated.json"
    wall_src = TDECODER_ARTIFACTS / "wall_ids.generated.json"
    assets_src = TDECODER_ARTIFACTS / "runtime_assets.generated.json"

    if tile_src.exists() and wall_src.exists():
        print(f"\n[3/3] Generating game_data.json from tile/wall metadata")
        tile_data = load_json(tile_src)
        wall_data = load_json(wall_src)
        runtime_assets = load_json(assets_src) if assets_src.exists() else {}
        game_data = build_game_data(tile_data, wall_data, runtime_assets)
        out_path = CDN_REPO / "pixel" / "game_data.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(game_data, f, ensure_ascii=False, indent=2)
        print(f"  -> {out_path}")
        print(f"  Tiles: {len(game_data['itemNames']['Tiles'])} names, {len(game_data['baseColors']['tiles'])} colors")
        print(f"  Walls: {len(game_data['itemNames']['Walls'])} names, {len(game_data['baseColors']['walls'])} colors")
        print(f"  Paints: {len(game_data['itemNames']['Paints'])} names")
    else:
        print(f"\n[3/3] SKIPPED game_data.json - tile/wall data not found")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
