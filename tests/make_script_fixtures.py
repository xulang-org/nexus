import copy, hashlib, json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/script-fixtures'
OUT.mkdir(parents=True,exist_ok=True)
TOOL=ROOT/'build/xu-nexus-script'
SCHEMA={'profile':'xu-scalar-v1','module':'scripts/player','class':'Player','fields':[{'id':1,'name':'ticks','type':'f64','default':0.0},{'id':2,'name':'distance','type':'f64','default':0.0}]}
counts={'valid':0,'rejected':0}

def source(body,fields=('ticks','distance'),module='scripts/player',class_name='Player'):
    return '@'+module+'\n\npub struct '+class_name+' {\n'+''.join('    pub '+f+' f64\n' for f in fields)+'}\n\nfn (self $&'+class_name+') physics_process(delta f64, axis f64) f64 {\n'+body+'\n}\n'

def compile_case(name,text,schema=SCHEMA,expected=None):
    s=OUT/(name+'.xus');m=OUT/(name+'.json');o=OUT/(name+'.xubc')
    s.write_text(text);m.write_text(json.dumps(schema))
    if expected is not None:o.write_bytes((OUT/'v1.xubc').read_bytes())
    before=o.read_bytes() if o.exists() else None
    result=subprocess.run([str(TOOL),'build',str(s),str(m),str(o)],capture_output=True,text=True,timeout=5)
    if expected is None:
        assert result.returncode==0,(name,result.stderr,result.stdout)
        counts['valid']+=1
    else:
        assert result.returncode!=0,(name,'incorrectly accepted')
        assert expected in result.stderr,(name,result.stderr)
        assert o.read_bytes()==before,(name,'overwrote last good artifact')
        counts['rejected']+=1
    return o

for label,speed in [('v1',180),('v2',360)]:
    compile_case(label,source('    self.ticks += 1.0\n    movement := axis * '+str(speed)+'.0 * delta\n    self.distance += movement\n    << movement'))
renamed=copy.deepcopy(SCHEMA);renamed['fields'][0]['name']='frames';renamed['fields'].append({'id':3,'name':'hp','type':'f64','default':100.0})
compile_case('rename-add',source('    self.frames += 1.0\n    movement := axis * 90.0 * delta\n    self.distance += movement\n    << movement',('frames','distance','hp')),renamed)
deleted=copy.deepcopy(renamed);deleted['fields'].pop(1)
compile_case('delete',source('    self.frames += 1.0\n    << axis * 90.0 * delta',('frames','hp')),deleted)
compile_case('alias',source('    $x := 1.0\n    y := x\n    x = 2.0\n    << y'))
compile_case('loop',source('    $x := 0.0\n    while x < 3.0 { x += 1.0 }\n    self.ticks += x\n    << x * delta'))
compile_case('branches',source('    $result := 0.0\n    if axis < -0.5 { result = -3.0\n    } else if axis > 0.5 { result = 3.0\n    } else { result = 2.0 }\n    << result'))
compile_case('short-circuit',source('    if false && 1.0 / 0.0 > 0.0 { << 999.0 }\n    if true || 1.0 / 0.0 > 0.0 { self.ticks += 1.0 }\n    << 2.0'))
compile_case('typed',source('    let $value: f64 = 1.5\n    let enabled: bool = true\n    if enabled { value *= 2.0 }\n    << value'))
compile_case('early-return',source('    if axis == 0.0 { << 0.0 }\n    << delta / axis'))
compile_case('boolean',source('    $flag := false\n    flag = true\n    if !flag { << 2.0 }\n    << 1.0'))
compile_case('divide-zero',source('    self.ticks += 1.0\n    << delta / 0.0'))
compile_case('overflow',source('    self.ticks += 1.0\n    << 1000000000.0 * 2.0'))
compile_case('host-bound',source('    self.ticks += 1.0\n    << 2048.0'))
compile_case('infinite',source('    while true { self.ticks += 1.0 }\n    << 0.0'))
foreign=copy.deepcopy(SCHEMA);foreign['module']='scripts/other'
compile_case('foreign',source('    << delta',module='scripts/other'),foreign)
empty=copy.deepcopy(SCHEMA);empty['fields']=[]
compile_case('empty-state',source('    << delta * axis * 2.0',fields=()),empty)

bad=[('syntax','@scripts/player\npub struct Player {',SCHEMA,'error:'),
 ('immutable',source('    x := 1.0\n    x = 2.0\n    << x'),SCHEMA,'mutable local'),
 ('argument-write',source('    delta = 0.0\n    << delta'),SCHEMA,'mutable local'),
 ('scope',source('    if true { x := 2.0 }\n    << x'),SCHEMA,'out-of-scope'),
 ('shadow',source('    if true { axis := 2.0 }\n    << axis'),SCHEMA,'shadowed'),
 ('int-literal',source('    << 1'),SCHEMA,'outside the scalar'),
 ('type',source('    << true'),SCHEMA,'type mismatch'),
 ('local-type',source('    let x: bool = 1.0\n    << 0.0'),SCHEMA,'local type'),
 ('call',source('    println("not executed")\n    << 0.0'),SCHEMA,'outside the scalar'),
 ('imports',source('    << 0.0').replace('\n\npub','\n#os\n\npub'),SCHEMA,'imports/compile tags'),
 ('no-return',source('    self.ticks += 1.0'),SCHEMA,'final return'),
 ('readonly',source('    << delta').replace('$&Player','&Player'),SCHEMA,'receiver'),
 ('hook',source('    << delta').replace('physics_process','process'),SCHEMA,'physics_process'),
 ('params',source('    << delta').replace('delta f64, axis f64','delta f64'),SCHEMA,'requires delta and axis'),
 ('huge',source('    << 10000000000.0'),SCHEMA,'constant outside'),
 ('infinity',source('    << 1e999'),SCHEMA,'constant outside scalar profile limits'),
 ('for',source('    for i in 0:3 { self.ticks += 1.0 }\n    << 0.0'),SCHEMA,'outside the scalar'),
 ('nesting',source('    '+'while true {\n'*70+'    self.ticks += 1.0\n'+'}\n'*70+'    << 0.0'),SCHEMA,'nesting limit')]
wrong_type=copy.deepcopy(SCHEMA);wrong_type['fields'][0]['type']='int';bad.append(('schema-type',source('    << delta'),wrong_type,'requires unique f64'))
dup=copy.deepcopy(SCHEMA);dup['fields'][1]['id']=1;bad.append(('schema-duplicate',source('    << delta'),dup,'duplicate field schema'))
for name,text,schema,expected in bad:compile_case('bad-'+name,text,schema,expected)

magic='XUNEXUS-SCRIPT-1\n'
base=json.loads((OUT/'v1.xubc').read_text().split('\n',1)[1]);rejected=[]
def invalid(name,change,needle,reference=None):
    d=copy.deepcopy(base if reference is None else reference);change(d);p=OUT/('invalid-'+name+'.xubc');p.write_text(magic+json.dumps(d));rejected.append((p.name,needle))
invalid('opcode',lambda d:d['code'][0].__setitem__(0,999),'unknown opcode')
invalid('jump',lambda d:d['code'][0].__setitem__(slice(None),[18,9999,0,0,1,1]),'jump target')
invalid('register',lambda d:d['code'][0].__setitem__(1,9999),'register operand')
invalid('argument',lambda d:d['code'][0].__setitem__(1,0),'register operand')
invalid('constant',lambda d:next(r for r in d['code'] if r[0]==1).__setitem__(2,999),'constant operand')
invalid('type',lambda d:d['registers'].__setitem__(2,2),'register operand/type')
invalid('location',lambda d:d['code'][0].__setitem__(4,0),'source location')
invalid('reserved',lambda d:d['code'][0].__setitem__(3,1),'reserved instruction')
invalid('field',lambda d:next(r for r in d['code'] if r[0]==4).__setitem__(2,99),'state load')
invalid('format',lambda d:d.__setitem__('format',999),'incompatible format')
invalid('api',lambda d:d.__setitem__('api',2),'incompatible format')
invalid('profile',lambda d:d.__setitem__('profile','other'),'incompatible format')
invalid('sourcehash',lambda d:d.__setitem__('source_hash','0'*63+'z'),'identity or resource')
invalid('fieldname',lambda d:d['fields'][0].__setitem__('name','not-valid'),'invalid state field')
invalid('duplicate-id',lambda d:d['fields'][1].__setitem__('id',1),'duplicate field')
invalid('default',lambda d:d['fields'][0].__setitem__('default',1e10),'invalid state field')
invalid('extra',lambda d:d.__setitem__('native',True),'object shape')
invalid('no-return',lambda d:d['code'].__setitem__(-1,[18,0,0,0,1,1]),'end with return')
invalid('boolean',lambda d:(d['registers'].append(2),d['code'].__setitem__(0,[2,len(d['registers'])-1,2,0,1,1])),'boolean literal')
# Structurally valid bytecode reading a not-yet-initialized register is a VM error.
uninit=copy.deepcopy(base);uninit['registers'].append(1);uninit['code'].insert(0,[20,0,len(uninit['registers'])-1,0,1,1]);uninit['functions'][0]['end']+=1;(OUT/'uninitialized.xubc').write_text(magic+json.dumps(uninit))
# Additional valid and rejected profiles below are included in the final summary.
reordered=copy.deepcopy(SCHEMA);reordered['fields'].reverse()
compile_case('reorder',source('    self.ticks += 1.0\n    movement := axis * 180.0 * delta\n    self.distance += movement\n    << movement'),reordered)
compile_case('bad-param-mark',source('    << delta').replace('delta f64','delta@ f64'),SCHEMA,'two distinct immutable f64')
compile_case('bad-lifetime',source('    << delta').replace('$&Player','$&a Player'),SCHEMA,'without lifetime annotations')
compile_case('bad-receiver-args',source('    << delta').replace('$&Player','$&Player#f64'),SCHEMA,'receiver state class mismatch')
signals=copy.deepcopy(SCHEMA);signals['signals']=[{'id':11,'name':'moved'},{'id':12,'name':'halted'}]
compile_case('signal-basic',source('    self.ticks += 1.0\n    emit_signal("moved", delta * 180.0)\n    emit_signal("halted", axis)\n    << delta'),signals)
renamed_signal=copy.deepcopy(signals);renamed_signal['signals'][0]['name']='motion';renamed_signal['signals'].reverse()
compile_case('signal-rename',source('    self.ticks += 1.0\n    emit_signal("motion", delta * 360.0)\n    << delta'),renamed_signal)
deleted_signal=copy.deepcopy(signals);deleted_signal['signals'].pop(0)
compile_case('signal-delete',source('    emit_signal("halted", axis)\n    << delta'),deleted_signal)
compile_case('signal-fail',source('    self.ticks += 1.0\n    emit_signal("moved", 7.0)\n    << delta / 0.0'),signals)
compile_case('signal-return-fail',source('    self.ticks += 1.0\n    emit_signal("moved", 7.0)\n    << 2048.0'),signals)
compile_case('signal-limit',source('    self.ticks += 1.0\n    $x := 0.0\n    while x < 33.0 { emit_signal("moved", x)\n    x += 1.0 }\n    << delta'),signals)
compile_case('signal-budget',source('    self.ticks += 1.0\n    emit_signal("moved", 7.0)\n    while true { self.distance += 1.0 }\n    << delta'),signals)
compile_case('signal-batch',source('    self.ticks += 1.0\n    $x := 0.0\n    while x < 32.0 { emit_signal("moved", x)\n    x += 1.0 }\n    << delta'),signals)
# Structurally typed emission with an uninitialized payload is still rejected
# dynamically, before either an event or state update can be committed.
uninit_signal=copy.deepcopy(base);uninit_signal['signals']=[{'id':11,'name':'moved'},{'id':12,'name':'halted'}]
uninit_signal['registers'].append(1)
uninit_signal['code'].insert(0,[21,0,len(uninit_signal['registers'])-1,0,1,1])
uninit_signal['functions'][0]['end']+=1
(OUT/'signal-uninitialized.xubc').write_text(magic+json.dumps(uninit_signal))
for name,body,needle in [
    ('unknown','    emit_signal("missing", 1.0)\n    << delta','not declared'),
    ('missing','    emit_signal("moved")\n    << delta','literal signal name'),
    ('extra','    emit_signal("moved", 1.0, 2.0)\n    << delta','exactly two'),
    ('nonliteral','    emit_signal(axis, 1.0)\n    << delta','literal signal name'),
    ('interpolated','    emit_signal("$axis", 1.0)\n    << delta','literal signal name'),
    ('bool','    emit_signal("moved", true)\n    << delta','type mismatch'),
    ('int','    emit_signal("moved", 1)\n    << delta','outside the scalar'),
    ('expression','    << emit_signal("moved", 1.0)','outside the scalar'),
    ('method','    self.emit_signal("moved", 1.0)\n    << delta','outside the scalar'),
    ('generic','    emit_signal#f64("moved", 1.0)\n    << delta','error:'),
    ('shadow','    emit_signal := 1.0\n    << delta','reserved signal intrinsic')]:
    compile_case('bad-signal-'+name,source(body),signals,needle)
for name,entries,needle in [
    ('duplicate-id',[{'id':11,'name':'a'},{'id':11,'name':'b'}],'duplicate signal schema'),
    ('duplicate-name',[{'id':11,'name':'a'},{'id':12,'name':'a'}],'duplicate signal schema'),
    ('invalid-id',[{'id':0,'name':'a'}],'invalid signal ID/name'),
    ('invalid-name',[{'id':11,'name':'bad-name'}],'invalid signal ID/name'),
    ('too-many',[{'id':i+1,'name':'s'+str(i)} for i in range(33)],'invalid signal schema'),
    ('type',{},'invalid signal schema'),
    ('extra',[{'id':11,'name':'a','type':'f64'}],'invalid schema object')]:
    schema=copy.deepcopy(SCHEMA);schema['signals']=entries
    compile_case('bad-signal-schema-'+name,source('    << delta'),schema,needle)
invalid('signal-index',lambda d:d['code'].__setitem__(0,[21,0,0,0,1,1]),'signal operand')
invalid('signal-reserved',lambda d:(d['signals'].append({'id':11,'name':'a'}),d['code'].__setitem__(0,[21,0,0,1,1,1])),'signal operand')
invalid('signal-payload',lambda d:(d['signals'].append({'id':11,'name':'a'}),d['registers'].append(2),d['code'].__setitem__(0,[21,0,len(d['registers'])-1,0,1,1])),'register operand/type')
invalid('signal-name',lambda d:d['signals'].append({'id':11,'name':'bad-name'}),'invalid signal ID/name')
invalid('signal-id',lambda d:d['signals'].append({'id':0,'name':'a'}),'invalid signal ID/name')
invalid('signal-duplicate',lambda d:d['signals'].extend([{'id':11,'name':'a'},{'id':11,'name':'b'}]),'duplicate signal ID/name')
invalid('signal-duplicate-name',lambda d:d['signals'].extend([{'id':11,'name':'a'},{'id':12,'name':'a'}]),'duplicate signal ID/name')
invalid('signal-limit',lambda d:d['signals'].extend([{'id':i+1,'name':'s'+str(i)} for i in range(33)]),'array limit')
old=copy.deepcopy(base);old['format']=1;old.pop('signals');old.pop('functions')
(OUT/'invalid-old-format.xubc').write_text('XUGAME-SCALAR-1\n'+json.dumps(old))
old2=copy.deepcopy(base);old2['format']=2;old2.pop('functions')
(OUT/'invalid-format-two.xubc').write_text('XUGAME-SCALAR-2\n'+json.dumps(old2))

retired=copy.deepcopy(base);retired['format']=3
(OUT/'invalid-format-three.xubc').write_text('XUGAME-SCALAR-3\n'+json.dumps(retired))
invalid('retired-format-number',lambda d:d.__setitem__('format',3),'incompatible format')

receiver={'profile':'xu-scalar-v1','module':'scripts/receiver','class':'Receiver',
          'fields':[{'id':i+1,'name':name,'type':'f64','default':0.0} for i,name in enumerate(('events','last','offset'))],
          'signals':[{'id':21,'name':'updated'}],
          'handlers':[{'id':41,'name':'on_moved'},{'id':42,'name':'on_other'}]}
def methods_source(methods,fields=('events','last','offset'),module='scripts/receiver',class_name='Receiver'):
    header='@'+module+'\n\npub struct '+class_name+' {\n'+''.join('    pub '+f+' f64\n' for f in fields)+'}\n'
    return header+''.join('\nfn (self $&'+class_name+') '+name+'('+params+') f64 {\n'+body+'\n}\n' for name,params,body in methods)
other=('on_other','value f64','    self.events += 10.0\n    self.last = -value\n    << value')
def receiver_methods(name='on_moved',gain=30,body=None):
    if body is None:body='    self.events += 1.0\n    self.last = value\n    self.offset = value * '+str(gain)+'.0\n    emit_signal("updated", self.offset)\n    << self.offset'
    return [(name,'value f64',body),other]
compile_case('receiver',methods_source(receiver_methods()),receiver)
receiver2=copy.deepcopy(receiver);receiver2['handlers'][0]['name']='on_motion';receiver2['handlers'].reverse()
compile_case('receiver-v2',methods_source(list(reversed(receiver_methods('on_motion',60)))),receiver2)
receiver_delete=copy.deepcopy(receiver);receiver_delete['handlers'].pop(0)
compile_case('receiver-delete',methods_source([other]),receiver_delete)
receiver_none=copy.deepcopy(receiver);receiver_none['handlers']=[]
compile_case('receiver-none',methods_source([('physics_process','delta f64, axis f64','    << delta')]),receiver_none)
compile_case('receiver-fail',methods_source(receiver_methods(body='    self.events += 1.0\n    emit_signal("updated", value)\n    << value / 0.0')),receiver)
compile_case('receiver-budget',methods_source(receiver_methods(body='    self.events += 1.0\n    emit_signal("updated", value)\n    while true { self.offset += 1.0 }\n    << value')),receiver)
compile_case('receiver-feedback',methods_source(receiver_methods(body='    self.events += 1.0\n    self.last = value\n    emit_signal("updated", value)\n    << value')),receiver)
limits=copy.deepcopy(receiver);limits['module']='scripts/limits';limits['class']='Limits';limits['fields']=[];limits['handlers']=[{'id':i+1,'name':'handle_'+str(i)} for i in range(16)]
limit_methods=[(h['name'],'value f64','    << value + '+str(i)+'.0') for i,h in enumerate(limits['handlers'])]
limit_methods.append(('physics_process','delta f64, axis f64','    << delta + axis'))
compile_case('function-limit',methods_source(limit_methods,fields=(),module='scripts/limits',class_name='Limits'),limits)
for name,text,schema,needle in [
    ('missing',methods_source([other]),receiver,'handler declarations differ'),
    ('undeclared',methods_source(receiver_methods('on_unknown')),receiver,'declared handler'),
    ('two-args',methods_source([('on_moved','value f64, second f64','    << value'),other]),receiver,'signal handler requires'),
    ('zero-args',methods_source([('on_moved','','    << 0.0'),other]),receiver,'one immutable f64'),
    ('duplicate',methods_source(receiver_methods()+[other]),receiver,'duplicate callback name'),
    ('local-scope',methods_source([('on_moved','value f64','    x := value\n    << x'),('on_other','value f64','    << x')]),receiver,'out-of-scope'),
    ('calls',methods_source(receiver_methods(body='    << on_other(value)')),receiver,'outside the scalar'),
    ('mutable',methods_source([('on_moved','$value f64','    << value'),other]),receiver,'error:'),
    ('return',methods_source(receiver_methods(body='    self.events += 1.0')),receiver,'final return')]:
    compile_case('bad-handler-'+name,text,schema,needle)
for name,entries,needle in [
    ('duplicate-id',[{'id':1,'name':'a'},{'id':1,'name':'b'}],'duplicate handler schema'),
    ('duplicate-name',[{'id':1,'name':'a'},{'id':2,'name':'a'}],'duplicate handler schema'),
    ('id',[{'id':0,'name':'a'}],'invalid handler ID/name'),
    ('name',[{'id':1,'name':'bad-name'}],'invalid handler ID/name'),
    ('reserved',[{'id':1,'name':'physics_process'}],'invalid handler ID/name'),
    ('intrinsic',[{'id':1,'name':'emit_signal'}],'invalid handler ID/name'),
    ('limit',[{'id':i+1,'name':'h'+str(i)} for i in range(17)],'invalid handler schema'),
    ('type',{},'invalid handler schema'),
    ('extra',[{'id':1,'name':'a','type':'f64'}],'invalid schema object')]:
    schema=copy.deepcopy(receiver);schema['handlers']=entries
    compile_case('bad-handler-schema-'+name,methods_source(receiver_methods()),schema,needle)
receiver_ir=json.loads((OUT/'receiver.xubc').read_text().split('\n',1)[1])
leak=copy.deepcopy(receiver_ir)
leak['code'][leak['functions'][1]['entry']]=[20,0,2,0,1,1]
(OUT/'receiver-register-leak.xubc').write_text(magic+json.dumps(leak))
invalid('function-start',lambda d:d['functions'][0].__setitem__('entry',1),'function name/code range')
invalid('function-end',lambda d:d['functions'][0].__setitem__('end',len(d['code'])+1),'function name/code range')
invalid('function-gap',lambda d:d['functions'][1].__setitem__('entry',d['functions'][1]['entry']+1),'function name/code range',receiver_ir)
invalid('function-kind',lambda d:d['functions'][0].__setitem__('kind',99),'function kind')
invalid('function-id',lambda d:d['functions'][0].__setitem__('id',3),'physics function identity')
invalid('function-empty',lambda d:d.__setitem__('functions',[]),'identity or resource')
invalid('function-limit',lambda d:d.__setitem__('functions',d['functions']*18),'array limit')
invalid('handler-id',lambda d:d['functions'][0].__setitem__('id',0),'handler identity',receiver_ir)
invalid('handler-duplicate',lambda d:d['functions'][1].__setitem__('id',41),'duplicate function',receiver_ir)
invalid('handler-argument',lambda d:d['code'].__setitem__(0,[3,2,1,0,1,1]),'register operand/type',receiver_ir)
invalid('cross-function-jump',lambda d:d['code'].__setitem__(0,[18,d['functions'][1]['entry'],0,0,1,1]),'jump target',receiver_ir)
(OUT/'reject-list.txt').write_text(''.join(p+'|'+needle+'\n' for p,needle in rejected))
print(f"Script fixtures: {counts['valid']} valid programs, {counts['rejected']} source/schema rejections preserving last artifact, {len(rejected)} invalid bytecode cases")
