from pathlib import Path
import copy, hashlib, json, subprocess, sys, os
R=Path.cwd();G=Path(os.environ.get('GRILLING_SOURCE',str(R.parent/'grilling'))).resolve()
sys.path.insert(0,str(R/'tools'))
from build_grilling_input import build
sha=lambda b:hashlib.sha256(b).hexdigest()
def read(p):return json.loads((R/p).read_text())
def write(p,d):(R/p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def replace(p,a,b):
 f=R/p;s=f.read_text();assert a in s,(p,a);f.write_text(s.replace(a,b))
baseline=json.loads((G/'baseline.json').read_text());assert baseline['version']==[2,8,219]
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=G,text=True).strip()
tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=G,text=True).strip()
assert commit=='53a5dea20e777367fe2d11137b07085ba9e752ef'
old=read('adapters/cookery-1.6.4-grilling-2.8.213-station-performance.json')
a=copy.deepcopy(old);a['id']='senluo-core:cookery-1.6.4-grilling-2.8.219-station-performance';a['toolkit_version']='0.32.0'
bp=G/baseline['runtime']['BP']
assert sha((bp/a['companion']['spec_path']).read_bytes())==a['companion']['spec_sha256']
for p,h in a['owned_helpers'].items():assert sha((bp/p).read_bytes())==h,p
c=a['companion'];c['version']=c['rp_version']=[2,8,219]
c['source'].update(commit=commit,git_tree=tree,resource_tree_sha256=baseline['source_trees']['RP']['sha256'],resource_file_count=baseline['source_trees']['RP']['files'])
c['runtime_trees']=baseline['source_trees'];c.pop('archive_sha256')
raw=build(G,a);c['archive_sha256']=sha(raw)
write('adapters/cookery-1.6.4-grilling-2.8.219-station-performance.json',a)
p=read('adapters/public-minimal-player.json');p['id']='senluo-core:public-minimal-g219-player';p['toolkit_version']='0.32.0'
p['recipe_version']='g219-to-g220-cookery20012-player-r1'
p['inputs']['grilling'].update(filename='grilling-2.8.219.mcaddon',sha256=sha(raw))
p['inputs']['cookery']['filename']='cookery-g219.mcaddon'
for row in p['packs']:
 if row['input']=='grilling':
  row['version']=[2,8,219]
  for module in row['modules']:module['version']=[2,8,219]
p['candidate_provenance'].update(grilling_commit=commit,grilling_git_tree=tree,grilling_input_archive_sha256=sha(raw),status='G219 canonical gameplay source; generated G220 player-complete local candidate; native/client acceptance pending')
p['player_presentation']['output_version']=[2,8,220]
p['player_presentation']['source']={'commit':commit,'git_tree':tree}
write('adapters/public-minimal-g219-player.json',p)
replace('tools/build_owned_family_recipe.py',"ROOT / 'adapters/public-minimal-player.json'","ROOT / 'adapters/public-minimal-g219-player.json'")
replace('tools/build_owned_family_recipe.py','grilling-2.8.213-station-performance.json','grilling-2.8.219-station-performance.json')
replace('tools/build_owned_family_recipe.py','reviewed G218 four-pack route','reviewed G220 four-pack route')
replace('tools/install_cookery_from_descriptor.py','grilling-2.8.212-station-performance.json','grilling-2.8.219-station-performance.json')
f=R/'tests/test_public_minimal.py';s=f.read_text()
s=s.replace("        source = json.loads((ROOT / 'adapters/public-minimal-grilling-g213-cookery20012.json').read_text())", "        adapter = json.loads(builder.PUBLIC_COOKERY_DESCRIPTOR.read_text())")
s=s.replace("        self.assertEqual(public['inputs']['cookery'], source['inputs']['cookery'])\n        self.assertEqual(public['inputs']['grilling'], source['inputs']['grilling'])", "        self.assertEqual(public['inputs']['grilling']['sha256'], adapter['companion']['archive_sha256'])\n        self.assertEqual(public['player_presentation']['source'], {key: adapter['companion']['source'][key] for key in ('commit', 'git_tree')})\n        for pack in public['packs']:\n            self.assertEqual(pack['version'], adapter['companion']['version'] if pack['input'] == 'grilling' else adapter['output_version'])")
# Retain the old G213 package-only test as explicit historical input, not an
# accidental requirement when the caller provides current G219 input archives.
s=s.replace("@unittest.skipUnless(os.environ.get('PUBLIC_MINIMAL_INPUTS'), 'Real public-minimal archives required')\n    def test_real_g213_pair_repeatability_and_manifest_closure(self):\n        inputs = Path(os.environ['PUBLIC_MINIMAL_INPUTS'])", "@unittest.skipUnless(os.environ.get('HISTORICAL_G213_INPUTS'), 'Historical G213 archives required')\n    def test_real_g213_pair_repeatability_and_manifest_closure(self):\n        inputs = Path(os.environ['HISTORICAL_G213_INPUTS'])")
f.write_text(s)
f=R/'.github/workflows/ci.yml';s=f.read_text().replace(old['companion']['source']['commit'],commit).replace('2.8.213','2.8.219').replace('cookery-g213','cookery-g219');f.write_text(s)
f=R/'docs/FAMILY-ASSEMBLY.md';s=f.read_text();current,history=s.split('## Current G212 installation',1)
current=current.replace('The previous G213 four-pack output','The historical G213 package-only four-pack output')
# Only current instructions change. Original failing G213 evidence remains named.
current=current.replace('The source input remains G213','The source input is now canonical G219').replace('2.8.218 (G218)','2.8.220 (G220)').replace('**Grilling G213**','**Grilling G219**').replace('complete G218','complete G220')
current=current.replace(old['companion']['source']['commit'],commit).replace(old['companion']['source']['git_tree'],tree).replace(old['companion']['archive_sha256'],sha(raw)).replace('2.8.213','2.8.219').replace('cookery-g213','cookery-g219')
current=current.replace('The fixed-input assembled output SHA256 is\n`9dca47ba396ede83a6dfd8146cef58474aa77555de154a400fe28289496ee822`.','The G219 input is checked against the new descriptor. The local output is\nG220; its hash is recorded by the actual assembler receipt, not inherited from\nthe historical G218 result. The unchanged Cookery20012 adapter bytes are\nretained because the exact host declaration and all 16 copied helpers match.\nReal-author reconstruction is checked separately from source-unit tests.')
current=current.replace('Reproduction succeeded without downloading IE, TACZ, Tavern or 世界名酒.','The public route does not download IE, TACZ, Tavern or 世界名酒.\nThe G213/G218 reproduction report remains historical evidence only.')
history=history.replace('## Historical recipes and package-only probes','## Historical recipes and package-only probes\n\n`public-minimal-player.json` preserves the previous G213 → G218 player-complete\nrecipe. Select it explicitly with the original source references; the new\ndefault is `public-minimal-g219-player.json`. Old descriptors and all previously\npublished identities remain unchanged.\n')
f.write_text(current+'## Current G212 installation'+history)
f=R/'README.md';s=f.read_text();a=s.index('**Status: implemented source candidate');b=s.index('\nLocal adaptation',a)
s=s[:a]+'''**Status: canonical G219 input → local G220 player-complete candidate.**
The public entry now includes the merged gameplay fixes, rather than asking
users to install the superseded G213 source. Four packs remain the complete
public set. Historical G213/G218 descriptors and their structural reports are
preserved, not relabeled as new G219 acceptance. Source tests and clean-author
reconstruction are separate from **NOT-RUN** native gameplay, rendering, audio,
saved-world upgrades and multiplayer. No public Release or LIVE change is
created by this source update.
'''+s[b:];f.write_text(s)
# New actual publication identity; do not mutate old payload hashes. Test and
# workflow sources remain outside the public allowlist, as the existing policy requires.
d=read('package.json');d['version']='0.32.0';write('package.json',d)
pub=read('PUBLICATION.json')
for name in ['adapters/cookery-1.6.4-grilling-2.8.219-station-performance.json','adapters/public-minimal-g219-player.json']:
 if name not in pub['files']:pub['files'].append(name)
pub['files'].sort();write('PUBLICATION.json',pub)
h=read('release-history.json');assert '0.32.0' not in h
h['0.32.0']={'toolkit_version':'0.32.0','sdk_version':'0.1.0','payloads':{n:sha((R/n).read_bytes()) for n in pub['files'] if n!='release-history.json'}}
write('release-history.json',h)
print(json.dumps({'grilling_input_sha256':sha(raw),'cookery_expected_unchanged_sha256':p['inputs']['cookery']['sha256'],'source':commit,'output':[2,8,220]},indent=2))
