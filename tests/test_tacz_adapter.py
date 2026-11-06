import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from install_tacz import adapt_files, apply_archive, repair_ui, repair_sound_definitions, repair_attachable_textures, source_sound_files, _source_files, repair_projectile_hit, FP, OFFHAND_FP
from assemble_family import read_definition


def encoded(value):
    return json.dumps(value).encode()


class TaczAdapterTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('TACZ_ORIGINAL_ARCHIVE'), 'Real author archives are supplied by the clean-input CI stage')
    def test_real_attachables_use_the_shipped_transparent_texture(self):
        prefix = 'TACZResour/'
        with zipfile.ZipFile(os.environ['TACZ_ORIGINAL_ARCHIVE']) as original, zipfile.ZipFile(os.environ['TACZ_ADAPTED_ARCHIVE']) as fixed:
            self.assertNotIn(prefix + 'textures/nothing.png', original.namelist())
            self.assertEqual(fixed.read(prefix + 'textures/ikon/empty.png'), original.read(prefix + 'textures/ikon/empty.png'))
            affected = []
            for path in original.namelist():
                if not path.startswith(prefix + 'attachables/') or not path.endswith('.json'):
                    continue
                before, after = read_definition(original.read(path)), read_definition(fixed.read(path))
                description = before['minecraft:attachable']['description']
                if description['textures'].get('default') == 'textures/nothing':
                    affected.append(description['identifier'])
                    description['textures']['default'] = 'textures/ikon/empty'
                    self.assertEqual(after, before)
                    target = after['minecraft:attachable']['description']['textures']['default']
                    self.assertIn(prefix + target + '.png', fixed.namelist())
                else:
                    self.assertEqual(fixed.read(path), original.read(path))
            self.assertEqual(len(affected), 82)
            self.assertTrue({'krep:g17', 'krep:g17_emp', 'krep:g18', 'krep:g18_emp'} <= set(affected))

    def test_attachable_texture_repair_preserves_geometry_animation_and_pixels(self):
        original = {'minecraft:attachable': {'description': {'identifier': 'krep:g17',
                    'textures': {'default': 'textures/nothing', 'enchanted': 'textures/misc/enchanted_item_glint'},
                    'geometry': {'default': 'geometry.itemscale'}, 'animations': {'hold': 'animation.itemscale'}}}}
        inputs = {'RP/attachables/g17.json': encoded(original),
                  'RP/textures/ikon/empty.png': b'author transparent pixels'}
        changed = repair_attachable_textures(inputs, 'RP/', {'texture_path_corrections': {'textures/nothing': 'textures/ikon/empty'}})
        self.assertEqual(set(changed), {'RP/attachables/g17.json'})
        output = read_definition(changed['RP/attachables/g17.json'])
        self.assertEqual(output['minecraft:attachable']['description']['textures']['default'], 'textures/ikon/empty')
        output['minecraft:attachable']['description']['textures']['default'] = 'textures/nothing'
        self.assertEqual(output, original)
        self.assertEqual(read_definition(inputs['RP/attachables/g17.json']), original)

    @unittest.skipUnless(os.environ.get('TACZ_ORIGINAL_ARCHIVE'), 'Real author archives are supplied by the clean-input CI stage')
    def test_real_hit_callback_preserves_damage_and_skips_removed_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            roots = []
            for kind, variable in [('original', 'TACZ_ORIGINAL_ARCHIVE'), ('fixed', 'TACZ_ADAPTED_ARCHIVE')]:
                root = Path(temporary) / kind
                root.mkdir()
                with zipfile.ZipFile(os.environ[variable]) as archive:
                    for name in ('projectileHitEntity.js', 'armorDetection.js'):
                        (root / name).write_bytes(archive.read('TACZBehavi/scripts/events/' + name))
                roots.append(str(root))
            # Execute the actual modules; only the native event/actor surface is
            # supplied here. Damage and armor logic remain the author's code.
            script = r"""
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),assert=require('node:assert/strict');
async function load(root){
 let callback; const sounds=[];
 class Player{playSound(s){sounds.push(s)}addTag(){}}
 const context=vm.createContext({Indoarsenal:{bullets:{akm:{damage:10,penetration:0.3}}}});
 const world={afterEvents:new Proxy({},{get:(_,name)=>({subscribe(fn){if(name==='projectileHitEntity')callback=fn}})})};
 const api={world,Player,GameMode:{creative:'creative'},EquipmentSlot:{},system:{runInterval(){return 1}}};
 const native=new vm.SyntheticModule(Object.keys(api),function(){for(const[k,v]of Object.entries(api))this.setExport(k,v)},{context});
 const modules=new Map();
 function module(file){if(!modules.has(file))modules.set(file,new vm.SourceTextModule(fs.readFileSync(file,'utf8'),{context,identifier:file}));return modules.get(file)}
 const main=module(path.join(root,'projectileHitEntity.js'));
 await main.link((name,ref)=>name==='@minecraft/server'?native:module(path.resolve(path.dirname(ref.identifier),name)));
 await main.evaluate();assert.equal(typeof callback,'function');
 function hit(valid,creative=false){
  const health={currentValue:20,setCurrentValue(n){this.currentValue=n}};
  const entity={isValid:()=>valid,matches(){if(!valid)throw Error('native removed target');return creative},hasTag:()=>false,getComponent:()=>health,getHeadLocation:()=>({x:0,y:1,z:0})};
  callback({getEntityHit:()=>({entity}),projectile:{typeId:'bullet:akm'},source:new Player(),location:{x:0,y:0,z:0}});
  return health.currentValue;
 }
 return hit;
}
(async()=>{const old=await load(process.argv[1]),fixed=await load(process.argv[2]);assert.throws(()=>old(false),/native removed target/);assert.equal(fixed(false),20);assert.equal(fixed(true),old(true));assert.equal(fixed(true),10);assert.equal(fixed(true,true),20);process.stdout.write('actual callback regression passed')})().catch(e=>{console.error(e);process.exit(1)});
"""
            self.assertEqual(subprocess.check_output(['node', '--experimental-vm-modules', '-e', script, *roots], text=True),
                             'actual callback regression passed')

    def test_projectile_target_is_validated_before_native_queries(self):
        from hashlib import sha256
        original = b"const hit=t=>{const _0x357e52=t;if(!_0x357e52||_0x357e52.matches({}))return;return 'damage';};"
        expected = original.replace(b'if(!_0x357e52||', b'if(!_0x357e52||!_0x357e52.isValid()||')
        fixed = repair_projectile_hit(original, {'prepared_sha256': sha256(original).hexdigest(),
                                                'output_sha256': sha256(expected).hexdigest()})
        script = fixed.decode() + "const gone={isValid:()=>false,matches:()=>{throw Error('removed')}};const live={isValid:()=>true,matches:()=>false};process.stdout.write(JSON.stringify([hit(gone),hit(live)]));"
        self.assertEqual(json.loads(subprocess.check_output(['node', '-e', script], text=True)), [None, 'damage'])

    def test_original_texture_bytes_are_required_without_replacing_item_icons(self):
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            texture = root / 'textures/gun/akm.png'
            texture.parent.mkdir(parents=True)
            texture.write_bytes(b'original gun pixels')
            descriptor = {'tacz': {'prefixes': {'RP': 'RP/'}}, 'restored_texture_files': {
                'textures/gun/akm.png': {'sha256': sha256(texture.read_bytes()).hexdigest()}}}
            self.assertEqual(_source_files(root, descriptor, 'texture'), {'RP/textures/gun/akm.png': b'original gun pixels'})
            texture.write_bytes(b'skinned pixels')
            with self.assertRaisesRegex(ValueError, 'Original author texture differs'):
                _source_files(root, descriptor, 'texture')

    def test_sound_reference_repair_keeps_volume_and_retires_only_declared_orphans(self):
        original = {'reload': {'category': 'player', 'sounds': [
            {'name': 'sounds/wrong/reload', 'volume': 0.7, 'pitch': [0.9, 1.1]}, 'sounds/kept']},
            'unfinished.weapon': {'sounds': ['sounds/not_shipped']}}
        result = json.loads(repair_sound_definitions(encoded(original), {
            'sound_path_corrections': {'sounds/wrong/reload': 'sounds/right/reload'},
            'retired_unused_sound_events': ['unfinished.weapon']}))
        self.assertEqual(result, {'reload': {'category': 'player', 'sounds': [
            {'name': 'sounds/right/reload', 'volume': 0.7, 'pitch': [0.9, 1.1]}, 'sounds/kept']}})

    def test_source_sound_requires_the_pinned_original_bytes(self):
        from hashlib import sha256
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'sounds/original.ogg'
            source.parent.mkdir()
            source.write_bytes(b'original author audio')
            descriptor = {'tacz': {'prefixes': {'RP': 'Author RP/'}},
                          'restored_sound_files': {'sounds/original.ogg': {
                              'sha256': sha256(source.read_bytes()).hexdigest()}}}
            self.assertEqual(source_sound_files(root, descriptor), {
                'Author RP/sounds/original.ogg': b'original author audio'})
            source.write_bytes(b'different audio')
            with self.assertRaisesRegex(ValueError, 'Original author sound differs'):
                source_sound_files(root, descriptor)
            with self.assertRaisesRegex(ValueError, 'requires --source-assets'):
                source_sound_files(None, descriptor)

    def test_ui_preserves_layout_and_uses_native_control_properties(self):
        layout = {'type': 'panel', 'offset': [0, '50%-68px'], 'controls': [{'stack': {'type': 'stack_panel'}}]}
        button = {'$button_text': '#form_button_text', 'color': '$button_color', 'bindings': [{'binding_name': '#button_enabled'}]}
        form = {'long_form': {'controls': [{'long_form@common_dialogs.main_panel_no_buttons': {
            'bindings': [{'binding_name': '#title_text'}, {'source_property_name': "((#title_text - 'Main') and (#title_text - 'Custom dial') = #title_text)"}]}}]},
            'button': {'controls': [{'form_button@common_buttons.light_text_button': button}]}}
        originals = {'RP/ui/hud_screen.json': encoded({'hud_actionbar_text': layout}),
                     'RP/ui/server_form.json': encoded(form)}
        before = copy.deepcopy(originals)
        result = repair_ui(originals, 'RP/')
        self.assertEqual(originals, before)
        hud = json.loads(result['RP/ui/hud_screen.json'])
        self.assertEqual(hud['namespace'], 'hud')
        self.assertEqual(hud['hud_actionbar_text'], {**layout, 'type': 'image', 'texture': 'textures/ikon/empty'})
        fixed = json.loads(result['RP/ui/server_form.json'])
        control = fixed['button']['controls'][0]['form_button@common_buttons.light_text_button']
        self.assertNotIn('color', control)
        self.assertEqual(control, {k: v for k, v in {**button, '$default_text_color': '$button_color'}.items() if k != 'color'})
        expression = fixed['long_form']['controls'][0]['long_form@common_dialogs.main_panel_no_buttons']['bindings'][1]['source_property_name']
        # Execute the produced predicate for all special titles and an ordinary form.
        js = expression.replace('#title_text', 'title').replace('not ', '!').replace(' and ', ' && ').replace(' = ', ' === ')
        code = "const f=Function('title','return '+process.argv[1]);process.stdout.write(JSON.stringify(['Custom dial','Custom triple','grip13','Main','Tavern','Custom dial extra'].map(f)));"
        self.assertEqual(json.loads(subprocess.check_output(['node', '-e', code, js], text=True)),
                         [False, False, False, False, True, True])

    def fixture(self):
        descriptor = {'toolkit_version': 'test', 'behavior_min_engine_version': [1, 26, 60],
                      'output_version': [1, 1, 20002],
                      'grilling': {'bp_uuid': 'g-bp', 'rp_uuid': 'g-rp', 'version': [2, 8, 206]},
                      'immersive_eating': {'bp_uuid': 'ie-bp', 'rp_uuid': 'ie-rp'},
                      'tacz': {'id': 'tacz:test', 'bp_uuid': 't-bp', 'rp_uuid': 't-rp',
                               'version': [1, 0, 3], 'output_version': [1, 0, 20002],
                               'prefixes': {'BP': 'Author BP/', 'RP': 'Author RP/'}}}
        originals = {}
        for side, uid, peer in [('BP', 't-bp', 't-rp'), ('RP', 't-rp', 't-bp')]:
            originals['Author ' + side + '/manifest.json'] = encoded({
                'format_version': 2,
                'header': {'uuid': uid, 'name': 'Author name', 'version': [1, 0, 3], 'min_engine_version': [1, 20, 0]},
                'modules': [{'uuid': uid + '-module', 'type': 'data' if side == 'BP' else 'resources', 'version': [1, 0, 3]}],
                'dependencies': [{'uuid': peer, 'version': [1, 0, 3]}, {'module_name': '@minecraft/server', 'version': '1.18.0'}],
                'metadata': {'authors': ['Original author']}})
        originals.update({'Author BP/entities/plalyer.json': b'original player',
                          'Author BP/entities/bullet/awp.json': b'// Original author comment.\n' + encoded({'minecraft:entity': {'components': {
                              'minecraft:break_blocks': {'breakable_blocks': ['glass', 'glass_panel', 'stained_glass', 'stained_glass_panel', 'wheat']},
                              'minecraft:physics': {}}}}),
                          'Author BP/scripts/main.js': b'original author script',
                          'Author RP/entity/player.entity.json': b'original client player',
                          'Author RP/animations/gun.json': b'original animation',
                          'Author RP/models/body.json': b'original model',
                          'Author RP/textures/skin.png': b'original pixels',
                          'Author RP/animation_controllers/g36.json': encoded({'animation_controllers': {
                              'controller.animation.g36.tp': {'states': {'slide': {
                                  'animations': [{'slide': 'v.g36'}, {'g36_tp_hold': 'v.g36'}],
                                  'transitions': [{'hold': "q.property('krep:movement')==0"}]}}}}}),
                          'Author RP/render_controllers/player.json': encoded({'render_controllers': {
                              FP: {'geometry': 'original-fp'}, 'controller.render.gun': {'geometry': 'unchanged-gun'},
                              'controller.render.player.universal.first_person': {'geometry':'Geometry.custom','part_visibility':[{'*':False},{'rightArm':'v.gun'},{'leftArm':'v.gun'},{'leftSleeve':'v.gun'}]}}})})
        schema = {'minecraft:entity': {'description': {'identifier': 'minecraft:player',
                  'properties': {'field:' + str(i): {'type': 'int', 'default': 0, 'range': [0, 1]} for i in range(28)}}}}
        composed = {'BP/entities/player.json': encoded(schema), 'RP/entity/player.entity.json': encoded({'minecraft:client_entity': {'description': {'identifier':'minecraft:player','render_controllers':[{FP:'v.is_first_person && !v.holding_all_guns'}]}}}),
                    'RP/animations/gun.json': b'conditioned left arm', 'RP/models/body.json': b'complete repaired model'}
        controller = encoded({'render_controllers': {FP: {'geometry': 'composed-nongun-fp', 'part_visibility':[{'*':False},{'rightArm':'v.right'},{'rightSleeve':'v.right'},{'leftArm':'v.left'},{'leftSleeve':'v.left'}]}}})
        return originals, composed, controller, descriptor

    def test_complete_pair_keeps_author_identity_scripts_pixels_and_gun_controller(self):
        originals, composed, controller, descriptor = self.fixture()
        before = copy.deepcopy(originals)
        result, receipt = adapt_files(originals, composed, controller, descriptor)
        self.assertEqual(originals, before)
        self.assertNotIn('Author BP/entities/plalyer.json', result)
        self.assertEqual(result['Author BP/entities/player.json'], composed['BP/entities/player.json'])
        self.assertTrue(result['Author BP/entities/bullet/awp.json'].startswith(b'// Original author comment.\n'))
        awp = read_definition(result['Author BP/entities/bullet/awp.json'])['minecraft:entity']['components']
        self.assertEqual(awp['minecraft:break_blocks']['breakable_blocks'],
                         ['glass', 'glass_pane', 'stained_glass', 'stained_glass_pane', 'wheat'])
        self.assertEqual(awp['minecraft:physics'], {})
        for name in ['Author BP/scripts/main.js', 'Author RP/textures/skin.png']:
            self.assertEqual(result[name], originals[name])
        self.assertEqual(result['Author RP/animations/gun.json'], composed['RP/animations/gun.json'])
        self.assertEqual(result['Author RP/models/body.json'], composed['RP/models/body.json'])
        controllers = json.loads(result['Author RP/render_controllers/player.json'])['render_controllers']
        self.assertEqual(controllers['controller.render.gun'], {'geometry': 'unchanged-gun'})
        self.assertEqual(controllers[FP], json.loads(controller)['render_controllers'][FP])
        gun=controllers['controller.render.player.universal.first_person']['part_visibility']
        self.assertEqual(gun[1], {'rightArm':'v.gun'})
        expression=gun[2]['leftArm']
        script="const f=Function('v','q','return '+process.argv[1]);process.stdout.write(JSON.stringify([false,true].flatMap(gun=>[false,true].map(held=>Boolean(f({gun},{is_item_equipped:()=>held}))))));"
        values=json.loads(subprocess.check_output(['node','-e',script,expression],text=True))
        self.assertEqual(values,[False,False,True,False])
        arm=json.loads(result['Author RP/render_controllers/kg_tacz_offhand.render_controllers.json'])['render_controllers'][OFFHAND_FP]
        self.assertEqual(arm['part_visibility'][1], {'rightArm':False})
        self.assertEqual(arm['part_visibility'][3], {'leftArm':'v.left'})
        client=json.loads(result['Author RP/entity/player.entity.json'])['minecraft:client_entity']['description']
        self.assertIn(OFFHAND_FP, client['render_controllers'][-1])
        self.assertEqual(client['particle_effects'], {
            'krep.shell': 'krep:762shell', 'krep.g3shell': 'krep:762shell',
            'krep.muzzlesmoke': 'krep:muzzlesmoke'})
        slide = json.loads(result['Author RP/animation_controllers/g36.json'])['animation_controllers']['controller.animation.g36.tp']['states']['slide']
        self.assertEqual(slide['animations'], [{'g36_tp_hold': 'v.g36'}])
        self.assertEqual(slide['transitions'], [{'hold': "q.property('krep:movement')==0"}])
        for side, uid in [('BP', 't-bp'), ('RP', 't-rp')]:
            manifest = json.loads(result['Author ' + side + '/manifest.json'])
            self.assertEqual(manifest['header']['uuid'], uid)
            self.assertEqual(manifest['header']['version'], [1, 0, 20002])
            self.assertEqual(manifest['modules'][0]['uuid'], uid + '-module')
            self.assertEqual(manifest['modules'][0]['version'], [1, 0, 20002])
            self.assertEqual(manifest['header']['min_engine_version'], [1, 26, 60])
            self.assertEqual(manifest.get('capabilities', []), ['pbr'] if side == 'RP' else [])
            self.assertIn({'module_name': '@minecraft/server', 'version': '1.18.0'}, manifest['dependencies'])
            self.assertIn({'uuid': 'g-' + side.lower(), 'version': [2, 8, 206]}, manifest['dependencies'])
            self.assertIn({'uuid': 'ie-' + side.lower(), 'version': [1, 1, 20002]}, manifest['dependencies'])
        self.assertEqual(receipt['player_properties'], 28)

    def test_projectile_repair_preserves_hits_physics_and_existing_cleanup(self):
        originals, composed, controller, descriptor = self.fixture()
        descriptor.update(remove_projectile_tick_world=True, repair_bullet_function_panes=True)
        bullet = {'minecraft:entity': {'description': {'identifier': 'bullet:akm'},
                  'components': {'minecraft:tick_world': {'radius': 2, 'distance_to_players': 128,
                                                         'never_despawn': False},
                                 'minecraft:projectile': {'power': 4, 'gravity': 0,
                                     'on_hit': {'impact_damage': {'damage': 10}, 'remove_on_hit': {}}},
                                 'minecraft:collision_box': {'width': 0.1, 'height': 0.1}},
                  'events': {'author:cleanup': {'remove': {'component_groups': ['author:bullet']}}}}}
        path = 'Author BP/entities/bullet/akm.json'
        originals[path] = encoded(bullet)
        without_tick = 'Author BP/entities/bullet/rpg.json'
        originals[without_tick] = encoded({'minecraft:entity': {'components': {
            'minecraft:projectile': {'power': 2, 'on_hit': {'explode': {'power': 3}}}}}})
        function = 'Author BP/functions/bullet.mcfunction'
        originals[function] = b'fill ~ ~ ~ ~1 ~1 ~1 air replace glass_panel\nfill ~ ~ ~ ~1 ~1 ~1 air replace stained_glass_panel\n'
        originals['Author BP/scripts/events/cleanup.js'] = b'original ten-tick cleanup'
        before = copy.deepcopy(originals)
        fixed, receipt = adapt_files(originals, composed, controller, descriptor)
        self.assertNotIn('minecraft:tick_world', read_definition(fixed[path])['minecraft:entity']['components'])
        self.assertEqual(read_definition(fixed[path])['minecraft:entity']['components']['minecraft:projectile'],
                         bullet['minecraft:entity']['components']['minecraft:projectile'])
        self.assertEqual(read_definition(fixed[path])['minecraft:entity']['components']['minecraft:collision_box'],
                         bullet['minecraft:entity']['components']['minecraft:collision_box'])
        self.assertEqual(read_definition(fixed[path])['minecraft:entity']['events'], bullet['minecraft:entity']['events'])
        self.assertEqual(fixed[without_tick], originals[without_tick])
        self.assertEqual(fixed['Author BP/scripts/events/cleanup.js'], originals['Author BP/scripts/events/cleanup.js'])
        self.assertEqual(fixed[function], originals[function].replace(b'glass_panel', b'glass_pane'))
        self.assertEqual(originals, before)

    def test_rejects_unreviewed_player_owner_over_limit_and_unknown_output(self):
        for damage in ('second-player', 'over-limit', 'unknown-output', 'missing-controller'):
            originals, composed, controller, descriptor = self.fixture()
            if damage == 'second-player': originals['Author BP/entities/player.json'] = b'foreign player'
            elif damage == 'over-limit':
                value = json.loads(composed['BP/entities/player.json'])
                value['minecraft:entity']['description']['properties'].update({str(i): {} for i in range(5)})
                composed['BP/entities/player.json'] = encoded(value)
            elif damage == 'unknown-output': composed['RP/../scripts/foreign.js'] = b'foreign'
            else: originals['Author RP/render_controllers/player.json'] = b'{}'
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                adapt_files(originals, composed, controller, descriptor)

    def test_archive_hash_is_checked_before_other_inputs_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'unreviewed.mcaddon'
            source.write_bytes(b'unreviewed')
            with self.assertRaisesRegex(ValueError, 'TACZ archive differs'):
                apply_archive(source, Path(directory) / 'missing-ie', Path(directory) / 'missing-g',
                              directory, {'tacz': {'archive_sha256': '0' * 64}})


if __name__ == '__main__':
    unittest.main()
