"""Reproducible public game sprites; no private app source or user save data.
Requires only Python 3 standard library. --check validates committed outputs.
"""
from pathlib import Path
import argparse, base64, hashlib, json, lzma, struct, zlib
root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(); parser.add_argument('--check', action='store_true'); args=parser.parse_args()
src=root/'sources/player-choices-v1'
encoded=''.join((src/f'part-{i}.txt').read_text().strip() for i in range(2))
assert len(encoded)==24364
packed=base64.b64decode(encoded,validate=True)
assert hashlib.sha256(packed).hexdigest()=='a129cd64a91bcb3210faf80cf2ab9a0a7541e20c60641b00bc845c8d7097a73b'
raw=lzma.decompress(packed,memlimit=256*1024*1024)
assert len(raw)==538422
width,height,count=struct.unpack('<IIH',raw[:10]);assert (width,height,count)==(640,840,203)
palette=[raw[10+i*4:14+i*4] for i in range(count)];pixels=raw[10+count*4:]
assert len(pixels)==width*height and max(pixels)<count
rgba=b''.join(palette[p] for p in pixels)
assert hashlib.sha256(rgba).hexdigest()=='d9af25346bd9e81cc9b816c277b7971b669f4ec36dbccb949d7934798960586f'
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
def output(path,content):
    if args.check: assert path.is_file() and path.read_bytes()==content, f'Generated resource differs: {path}'
    else: path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
folder=root/'player/1.4.5.8/choices-v1'; entries=[]
for i in range(240):
    key=f'hair-{i}' if i<228 else f'clothes-{i-228}'
    x=i%16*40;y=i//16*56
    rows=[rgba[((y+r)*width+x)*4:((y+r)*width+x+40)*4] for r in range(56)]
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',40,56,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+row for row in rows),9))+chunk(b'IEND',b'')
    output(folder/f'{key}.png',png)
    entries.append({'path':f'{key}.png','bytes':len(png),'sha256':hashlib.sha256(png).hexdigest(),'rgbaSha256':hashlib.sha256(b''.join(rows)).hexdigest()})
manifest={'schema':1,'assetVersion':'choices-v1','gameVersion':'1.4.5.8','kind':'player-creation-preview','width':40,'height':56,'count':240,'source':'PlayerWebsite@9e09f4e3aef37befc267aa51c190bea472726c8b player atlas, generated standing previews','sourceRgbaSha256':hashlib.sha256(rgba).hexdigest(),'assets':entries}
output(folder/'manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
# Existing legacy assets are audited rather than falsely relabelled as this game version.
items=sorted(root.glob('items/Item_*.png')); nums=[int(p.stem[5:]) for p in items if p.stem[5:].isdigit()]
registry={'schema':1,'repository':'Live-yan/terraviewer-images','legacySourceCommit':'d8b7a655e210fe377186a083635733ece85c3594','legacyGameVersion':None,'items':{'path':'items/Item_{id}.png','count':len(nums),'highestId':max(nums,default=0)},'data':{'chestCatalog':'index/chest_items.json','bestiary':'index/bestiary.json','gameData':'pixel/game_data.json','colorIndex':'pixel/terraria_color_index.txci.gz'},'playerChoices':{'path':'player/1.4.5.8/choices-v1','gameVersion':'1.4.5.8','count':240},'policy':'Clients pin an immutable Git commit; fallback keeps the same revision. User files, font files and executable runtime are not part of this manifest.'}
for value in registry['data'].values(): assert (root/value).is_file(), value
output(root/'index/resources-v1.json',(json.dumps(registry,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({'verified':args.check,'sprites':len(entries),'bytes':sum(x['bytes'] for x in entries),'legacyItemCount':len(nums),'legacyHighestId':max(nums,default=0)}))
