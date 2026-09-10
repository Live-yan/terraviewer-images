# Player creation preview source

Lossless indexed RGBA source for 228 hairstyles and 12 clothing previews (40×56 each), generated from the fixed PlayerWebsite 1.4.5.8 atlas. These are public game-art previews, not player saves. `part-0.txt` + `part-1.txt` are one Base64/LZMA stream, decoded and SHA-256 verified by `scripts/build-player-choices.py`. No network access or third-party Python dependency is required to regenerate the PNGs.

Run `python scripts/build-player-choices.py` to build, or add `--check` to compare every committed PNG and manifest. Existing world/item resources are retained without claiming they have been upgraded to 1.4.5.8.
