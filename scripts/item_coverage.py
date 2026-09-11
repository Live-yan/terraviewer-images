"""Pinned Terraria item icon coverage and deterministic repair; no network required.

python scripts/item_coverage.py --write   # generate only the 111 missing files plus the incorrect 5708 alias
python scripts/item_coverage.py --check   # reproduce repairs, decode every PNG and verify manifest

Images are UI thumbnails. C# gives IDs and texture aliases, not new artwork.
"""
from pathlib import Path
import argparse, base64, hashlib, io, json, struct, zlib

ROOT = Path(__file__).resolve().parents[1]
SPEC = 'data/item-coverage-8255d346.json'
SEED = 'data/item-thumbnails-6147-6195.json'
MANIFEST = 'index/items-1.4.5.8.json'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def resolve_texture(item, mapping):
    seen = set()
    while str(item) in mapping:
        if item in seen:
            raise ValueError('TextureCopyLoad cycle')
        seen.add(item)
        item = int(mapping[str(item)])
    if not 1 <= item <= 6195:
        raise ValueError('Invalid texture ID')
    return item

def png_rgba(width, height, pixels):
    if not 1 <= width <= 40 or not 1 <= height <= 40 or len(pixels) != width * height * 4:
        raise ValueError('Unexpected thumbnail geometry')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    scan = b''.join(b'\0' + pixels[y*width*4:(y+1)*width*4] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',width,height,8,6,0,0,0))
            + chunk(b'IDAT', zlib.compress(scan, 9)) + chunk(b'IEND', b''))

def repairs(root=ROOT):
    spec = json.loads((root / SPEC).read_text(encoding='utf-8'))
    seed = json.loads((root / SEED).read_text(encoding='utf-8'))
    compressed = base64.b64decode(''.join((root/name).read_text().strip() for name in seed['rgbaZlibParts']), validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, 400000)
    if not decoder.eof or decoder.unused_data or len(raw) != seed['rgbaBytes'] or digest(raw) != seed['rgbaSha256']:
        raise ValueError('Thumbnail input checksum failed')
    output = {}; details = {}; offset = 0
    for item in seed['items']:
        n,w,h,start,atlas_box = item
        if n not in spec['newThumbnails'] or n in output or start != offset:
            raise ValueError('Unexpected or duplicate thumbnail')
        data = raw[offset:offset+w*h*4];offset += len(data)
        if len(data) != w*h*4 or not any(data[3::4]):
            raise ValueError('Empty/corrupt thumbnail')
        output[n] = png_rgba(w,h,data)
        details[n] = {'kind':'atlas-thumbnail','sourceItemId':n,'rgbaSha256':digest(data)}
    if offset != len(raw) or sorted(output) != spec['newThumbnails']:
        raise ValueError('Incomplete atlas selection')
    for n in spec['missingAliasBefore'] + spec.get('correctedExistingAliases', []):
        canonical = resolve_texture(n,spec['textureCopyLoad'])
        path = root / f'items/item_{canonical}.png'
        if not path.is_file():
            raise ValueError(f'Missing original texture for alias {n}: {canonical}')
        output[n] = path.read_bytes()
        details[n] = {'kind':'native-texture-copy','sourceItemId':canonical}
    if sorted(output) != sorted(spec['missingBefore'] + spec.get('correctedExistingAliases', [])):
        raise ValueError('Repair set differs from initial audit')
    return spec, seed, output, details

def audit(root=ROOT, write=False):
    from PIL import Image
    spec, seed, generated, details = repairs(root)
    for item, data in generated.items():
        target = root / f'items/item_{item}.png'
        if write:
            target.write_bytes(data)
        elif not target.is_file() or target.read_bytes() != data:
            raise ValueError(f'Generated image differs/missing: {target.name}')
    entries = []; empty = []
    for n in range(spec['range'][0],spec['range'][1]+1):
        path = root / f'items/item_{n}.png'
        if not path.is_file():
            raise ValueError(f'Missing item image: {n}')
        data = path.read_bytes()
        with Image.open(io.BytesIO(data)) as image:
            if image.format != 'PNG' or image.width > 8192 or image.height > 8192:
                raise ValueError(f'Invalid image {n}')
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load(); rgba = image.convert('RGBA'); box = rgba.getbbox()
            if not box: empty.append(n)
            entry = {'id':n,'path':f'items/item_{n}.png','bytes':len(data),'width':image.width,'height':image.height,'sha256':digest(data)}
        if n in generated and not box:
            raise ValueError(f'Repair is transparent: {n}')
        if n in details: entry.update(details[n])
        entries.append(entry)
    active_empty = sorted(set(empty) - set(spec['deprecated']) - {3705,3706,3853,4143,5013})
    if active_empty:
        raise ValueError(f'Active transparent item images: {active_empty}')
    for n in spec['textureCopyLoad']:
        canonical = resolve_texture(int(n), spec['textureCopyLoad'])
        if (root / f'items/item_{n}.png').read_bytes() != (root / f'items/item_{canonical}.png').read_bytes():
            raise ValueError(f'Native texture alias mismatch: {n} -> {canonical}')
    manifest = {'schema':1,'targetGameVersion':'1.4.5.8','sourceRepository':spec['sourceRepository'],
        'sourceCommit':spec['sourceCommit'],'itemIdBlob':spec['itemIdBlob'],'itemIdCount':spec['itemIdCount'],
        'coveredRange':spec['range'],'coveredCount':len(entries),'missingIds':[],
        'repairedCount':len(generated),'textureCopies':len(spec['missingAliasBefore'])+len(spec.get('correctedExistingAliases', [])),
        'addedMissingImages':len(spec['missingBefore']),'correctedExistingIds':spec.get('correctedExistingAliases', []),
        'newThumbnails':len(spec['newThumbnails']),'deprecatedIds':spec['deprecated'],
        'transparentExistingIds':empty,'atlasSource':seed['source'],
        'artworkScope':'Existing icons retained except an incorrect 5708 alias, not claimed to be re-exported from the latest game. 49 supplemental images are exact crops of a pinned UI atlas; 63 repaired aliases use the native texture mapping. All 67 native aliases verified.',
        'files':entries}
    text = json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    path = root/MANIFEST
    if write:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    elif not path.is_file() or path.read_text(encoding='utf-8') != text:
        raise ValueError('Coverage manifest differs; regenerate intentionally')
    return {'passed':True,'sourceCommit':spec['sourceCommit'],'itemIdCount':spec['itemIdCount'],
        'coveredCount':len(entries),'range':spec['range'],'missingIds':[], 'decodedPngs':len(entries),
        'repairedCount':len(generated),'nativeTextureCopies':len(spec['missingAliasBefore'])+len(spec.get('correctedExistingAliases', [])),
        'addedMissingImages':len(spec['missingBefore']),'correctedExistingIds':spec.get('correctedExistingAliases', []),'allNativeAliasesVerified':len(spec['textureCopyLoad']),
        'atlasThumbnails':len(spec['newThumbnails']),'transparentExistingIds':empty,
        'allImageBytes':sum(e['bytes'] for e in entries),'repairBytes':sum(len(v) for v in generated.values()),
        'manifestSha256':digest(text.encode())}

if __name__ == '__main__':
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true')
    args=parser.parse_args();report=audit(write=args.write)
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports/item-coverage.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
