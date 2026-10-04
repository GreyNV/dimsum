import test from 'node:test';
import assert from 'node:assert/strict';
import {visualHash, residentBounds, cameraView, follow, retainResident, tileAt, Controls, TILE_W, TILE_H} from '../src/dimensional_sim/world/browser/view.js';
import {groundMarks, paintChunk, TREE, terrainColor, OBJECT_PAD, clearStamps, stampCount, TILE_VARIANTS, TREE_VARIANTS, ROCK_VARIANTS} from '../src/dimensional_sim/world/browser/art.js';
import {playerSprite, ENEMY, ROLE, spriteSize, mirrorSprite, paintSprite, punchReach, hiddenBehind, occludingTreeTiles, SPOTS, POSE, crouchSprite, drawSpot, CAMP} from '../src/dimensional_sim/world/browser/actors.js';
import {activityText, newRewards, ATTRIBUTES, rewardTexts, reportIsFresh} from '../src/dimensional_sim/world/browser/hud.js';
const pose = (facing, animation='idle', animation_ms=0) => ({facing, animation, animation_ms, active:false});
const chunk = (x=0,y=0) => ({id:'forest:'+x+':'+y,x,y,width:32,height:16,seed:1234,
  tiles:Array(16).fill('.'.repeat(32)),collision:Array(16).fill('0'.repeat(32))});

test('visual detail repeats exactly for negative global coordinates and varies with seed',()=>{
  assert.equal(visualHash(-123,41,482910),visualHash(-123,41,482910));
  assert.notEqual(visualHash(-123,41,482910),visualHash(-123,41,482911));
  assert.deepEqual(groundMarks(';',-33,-17,123),groundMarks(';',-33,-17,123));
  assert.notDeepEqual(groundMarks(';',-33,-17,123),groundMarks(';',-33,-17,124));
  for(const mark of groundMarks('=',0,0,123)) {
    assert.ok(mark.col>=0 && mark.col<6 && mark.row>=0 && mark.row<4);
    assert.equal(mark.glyph.length,1); assert.match(mark.color,/^#[0-9a-f]{6}$/);
  }
});
test('camera never exposes beyond resident data at browser, mobile and 4K sizes',()=>{
  const chunks=[];
  for(let y=-1;y<=1;y++)for(let x=-1;x<=1;x++)chunks.push(chunk(x,y));
  const bounds=residentBounds(chunks);
  for(const [width,height] of [[1440,1024],[390,844],[3840,2160]]) {
    for(const position of [{x:-10000,y:-10000},{x:0,y:0},{x:10000,y:10000}]) {
      const v=cameraView(position,width,height,.7,bounds);
      assert.ok(v.x-width/v.scale/2>=bounds.left-1e-8);
      assert.ok(v.x+width/v.scale/2<=bounds.right+1e-8);
      assert.ok(v.y-height/v.scale/2>=bounds.top-1e-8);
      assert.ok(v.y+height/v.scale/2<=bounds.bottom+1e-8);
    }
  }
});
test('camera follows global positions continuously across a negative chunk boundary',()=>{
  let camera=-.5*TILE_W;
  const next=follow(camera,.5*TILE_W,16);
  assert.ok(next>camera && next<.5*TILE_W);
  assert.ok(Math.abs(follow(follow(camera,100,8),100,8)-follow(camera,100,16))<1e-10);
});
test('resident cache drops stale surfaces; collision lookup uses authoritative metadata',()=>{
  const a=chunk(-1,-1), b=chunk(0,0);
  a.tiles[15]='.'.repeat(31)+'T';
  a.collision[15]='0'.repeat(32); // Deliberate mismatch: glyph must not imply collision.
  const cache=new Map([[a.id,a],[b.id,b]]);
  assert.deepEqual(tileAt([...cache.values()],-1,-1),{glyph:'T',blocked:false});
  assert.equal(tileAt([...cache.values()],1000,1000),null);
  retainResident(cache,[b.id]);assert.deepEqual([...cache.keys()],[b.id]);
});
test('short attack press remains queued across polling gap until acknowledged',()=>{
  const input=new Controls();
  input.attack(true);input.attack(false);
  const sent=input.payload(false,[]);
  assert.equal(sent.attack,true);
  assert.equal(input.payload(false,[]).attack,true);
  input.acknowledge(sent);
  assert.equal(input.payload(false,[]).attack,false);
});
test('movement prioritizes latest held key; pause and reset release all input',()=>{
  const input=new Controls();
  input.press('w','north'); input.press('d','east');input.press('w','north');
  assert.equal(input.payload(false,[]).move,'east');
  input.release('d');assert.equal(input.payload(false,[]).move,'north');
  input.attack(true);
  assert.deepEqual(input.payload(true,['x']),{move:null,attack:false,paused:true,known:['x']});
  input.reset();assert.deepEqual(input.payload(false,[]),{move:null,attack:false,paused:false,known:[]});
});
test('character art is multi-cell; cached ground and objects paint separately without actors',()=>{
  assert.ok(TREE.length>4 && TREE.some(row=>row.length>6));
  const logs=[];
  const factory=()=> {
    const log=[];logs.push(log);
    const canvas={width:0,height:0,log,getContext:()=>({set font(v){},set textBaseline(v){},set textAlign(v){},set fillStyle(v){},
      fillRect:(...a)=>log.push(['rect',...a]),fillText:(...a)=>log.push(['text',...a]),drawImage:(img,...a)=>log.push(['image',img,...a])})};
    return canvas;
  };
  clearStamps();
  const asset=chunk();asset.tiles[0]='T^' + '.'.repeat(30);
  const pictures=paintChunk(asset,factory);
  assert.equal(pictures.ground.width,32*TILE_W);
  assert.equal(pictures.objects.height,16*TILE_H+OBJECT_PAD*2);
  const groundLog=pictures.ground.log, objectLog=pictures.objects.log;
  assert.equal(groundLog.filter(e=>e[0]==='image').length,32*16,'one stamp copy per tile');
  assert.equal(objectLog.filter(e=>e[0]==='image').length,2,'tree and rock stamps');
  assert.ok(groundLog.every(e=>e[0]==='image'),'no per-glyph text on the chunk surface');
  const stamped=logs.filter(l=>l!==groundLog&&l!==objectLog);
  assert.ok(stamped.some(l=>l.some(e=>e[0]==='text')),'stamps carry the character art');
  assert.ok(stampCount()<=TILE_VARIANTS*3+TREE_VARIANTS+ROCK_VARIANTS);
  const again=paintChunk(asset,factory);
  assert.equal(stampCount(),new Set(stamped).size,'stamps are reused, not redrawn');
  assert.deepEqual(again.ground.log.map(e=>e[1]),groundLog.map(e=>e[1]),'same variant per coordinate');
  assert.notEqual(terrainColor('='),terrainColor('T'));
});

test('a second tap during an in-flight attack survives acknowledgement and sends a release edge',()=>{
  const input=new Controls();
  input.attack(true);input.attack(false);
  const first=input.payload(false,[]), revision=input.attackRevision;
  input.attack(true);input.attack(false);
  input.acknowledge(first,revision);
  const release=input.payload(false,[]);
  assert.equal(release.attack,false);
  input.acknowledge(release);
  const second=input.payload(false,[]);
  assert.equal(second.attack,true);
  input.acknowledge(second);
  assert.equal(input.payload(false,[]).attack,false);
});

test('actor sprites are well-formed rectangles with defined color roles in every pose',()=>{
  const sprites=[ENEMY];
  for(const f of ['north','east','south','west']) for(const [a,ms] of [['idle',0],['walk',0],['walk',130],['attack',100]]) sprites.push(playerSprite(pose(f,a,ms)));
  for(const s of sprites) {
    assert.equal(s.paint.length,s.glyph.length);
    const w=s.paint[0].length;
    s.paint.forEach((row,r)=>{assert.equal(row.length,w);assert.equal(s.glyph[r].length,w);
      for(const role of row) assert.ok(role===' ' || ROLE[role],'unknown role '+role);});
  }
});
test('actors are large enough to read against terrain (size regression guard)',()=>{
  for(const f of ['north','east','south','west']) {
    const {width,height}=spriteSize(playerSprite(pose(f)));
    assert.ok(width>=TILE_W*1.5 && height>=TILE_H*2,`player ${f} ${width}x${height}`);
  }
  const enemy=spriteSize(ENEMY);
  assert.ok(enemy.width>=TILE_W*1.5 && enemy.height>=TILE_H*1.5);
  const filled=ENEMY.paint.join('').replace(/ /g,'').length;
  assert.ok(filled>=40,'enemy silhouette must be solid, not sparse glyphs');
});
test('west view mirrors east; walking changes legs; attack poses differ by phase',()=>{
  assert.deepEqual(playerSprite(pose('west')),mirrorSprite(playerSprite(pose('east'))));
  assert.notDeepEqual(playerSprite(pose('south','walk',0)),playerSprite(pose('south','walk',130)));
  const attack={...pose('east','attack',100)};
  const reach=['windup','strike','recover'].map(p=>punchReach(attack,p));
  assert.equal(new Set(reach).size,3);
  assert.ok(reach[1]>reach[2] && reach[2]>reach[0],'strike extends furthest, windup pulls back');
  assert.equal(punchReach(pose('east','idle'),'strike'),null,'no weapon or fist when not attacking');
});
test('flash paints a silhouette without glyph texture; dissolve removes cells stably',()=>{
  const log=[], ctx={fillRect:(...a)=>log.push(['rect',...a]),fillText:(...a)=>log.push(['text',...a]),set fillStyle(v){},set globalAlpha(v){}};
  paintSprite(ctx,ENEMY,0,0,{flash:true});
  assert.equal(log.filter(e=>e[0]==='text').length,0);
  const count=opts=>{const l=[];paintSprite({...ctx,fillRect:()=>l.push(1),fillText:()=>{}},ENEMY,0,0,opts);return l.length;};
  assert.ok(count({dissolve:.5,seed:9})<count({}));
  assert.equal(count({dissolve:.5,seed:9}),count({dissolve:.5,seed:9}));
});
test('x-ray and canopy occlusion are presentation helpers from authoritative tiles',()=>{
  assert.ok(hiddenBehind({x:5,y:4,hp:2},{x:5,y:5}));
  assert.ok(!hiddenBehind({x:5,y:6,hp:2},{x:5,y:5}));
  assert.ok(!hiddenBehind({x:5,y:4,hp:0},{x:5,y:5}));
  const tiles=occludingTreeTiles(-3,-7);
  assert.equal(tiles.length,6);
  assert.ok(tiles.every(t=>t.y>-7 && Math.abs(t.x+3)<=1));
});

test('movement taps between polls reach the server once each, separated by a release',()=>{
  const input=new Controls();
  input.press('d','east');input.release('d');
  const first=input.payload(false,[]);assert.equal(first.move,'east');
  input.acknowledge(first);
  assert.equal(input.payload(false,[]).move,null);
  input.press('d','east');input.release('d');input.press('d','east');input.release('d');
  const edge=input.payload(false,[]);assert.equal(edge.move,null);input.acknowledge(edge);
  const second=input.payload(false,[]);assert.equal(second.move,'east');input.acknowledge(second);
  const gap=input.payload(false,[]);assert.equal(gap.move,null);input.acknowledge(gap);
  const third=input.payload(false,[]);assert.equal(third.move,'east');input.acknowledge(third);
  assert.equal(input.payload(false,[]).move,null);
  input.press('w','north');input.reset();assert.equal(input.payload(false,[]).move,null);
});

test('encounter spot sprites are well-formed and activity poses crouch the body',()=>{
  for(const [id,s] of Object.entries(SPOTS)) {
    assert.equal(s.paint.length,s.glyph.length,id);
    s.paint.forEach((row,r)=>{assert.equal(row.length,s.paint[0].length,id);assert.equal(s.glyph[r].length,row.length,id);});
  }
  for(const id of ['bramble_berries','fallen_branches','animal_tracks','gnarled_tree','forest_spring','mossy_stone','old_carvings']) assert.ok(SPOTS[id],id);
  const standing=playerSprite(pose('south')), crouched=crouchSprite(standing);
  assert.ok(spriteSize(crouched).height<spriteSize(standing).height);
  assert.equal(crouched.paint.at(-1),standing.paint.at(-1),'boots stay on the ground');
  for(const kind of ['forage','gather','observe','climb','drink','meditate','study']) assert.ok(POSE[kind],kind);
  const calls=[];const ctx=new Proxy({},{get:(_,k)=>k==='save'||k==='restore'||k==='fillRect'||k==='fillText'?(...a)=>calls.push(k):undefined,set:()=>true});
  drawSpot(ctx,{encounter:'unknown',x:0,y:0},0,0); assert.equal(calls.length,0,'unknown spots draw nothing');
});
test('HUD describes the auto-pilot from snapshot fields only',()=>{
  const base={spots:[{x:3,y:4,name:'Bramble berries'}],expedition:{mode:'travel',goal:{x:3,y:4},activity:null,control:'auto',log:[],xp:{},skills:[]}};
  assert.equal(activityText(base),'Heading for bramble berries');
  assert.equal(activityText({...base,expedition:{...base.expedition,activity:{name:'Forest spring',kind:'drink',progress:456}}}),'Drinking at forest spring - 45%');
  assert.match(activityText({...base,expedition:{...base.expedition,mode:'fight'}}),/punching/);
  assert.equal(activityText(base,true),'Paused - the forest can wait');
  assert.equal(activityText({}),null,'legacy manual frames fall back');
  const log=[{seq:4},{seq:5},{seq:6}];
  assert.deepEqual(newRewards({expedition:{log}},4).map(e=>e.seq),[5,6]);
  assert.equal(ATTRIBUTES.length,6);
});

test('HUD turns log entries into reward popups and shows reports only while fresh',()=>{
  const enc={type:'encounter',xp:40,attribute:'perception',items:[['wild_berries',3]],text:'x'};
  assert.deepEqual(rewardTexts(enc).map(r=>r.text),['+40 Perception','+3 wild berries']);
  assert.deepEqual(rewardTexts({type:'eat',text:'Ate boar meat (+35 hunger, +11 health).',items:[['boar_meat',-1]]}).map(r=>r.text),['boar meat (+35 hunger, +11 health)']);
  assert.ok(reportIsFresh({total_ms:5000,report:{clock_ms:0}}),'intro on a fresh world');
  assert.ok(!reportIsFresh({total_ms:600000,report:{clock_ms:0}}),'no stale report on reload');
  const base={expedition:{mode:'home',goal:null,activity:null,control:'auto',depth:2}};
  assert.match(activityText(base),/anchor camp/);
  assert.match(activityText({expedition:{...base.expedition,mode:'rest',activity:{kind:'rest',name:'Resting',progress:500}}}),/Resting at the anchor camp - 50%/);
  for(const [id,s] of Object.entries(CAMP)) s.paint.forEach((row,r)=>{assert.equal(row.length,s.paint[0].length,id);assert.equal(s.glyph[r].length,row.length,id);});
  assert.equal(POSE.rest,'sit');
});
