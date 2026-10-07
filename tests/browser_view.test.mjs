import test from 'node:test';
import assert from 'node:assert/strict';
import {visualHash, residentBounds, cameraView, follow, retainResident, tileAt, stickDirection, Controls, TILE_W, TILE_H} from '../src/dimensional_sim/world/browser/view.js';
import {groundMarks, paintChunk, TREE, terrainColor, OBJECT_PAD, clearStamps, stampCount, TILE_VARIANTS, TREE_VARIANTS, ROCK_VARIANTS} from '../src/dimensional_sim/world/browser/art.js';
import {ENEMY, ROLE, spriteSize, paintSprite, punchReach, hiddenBehind, occludingTreeTiles, SPOTS, POSE, drawSpot, CAMP, ELDER} from '../src/dimensional_sim/world/browser/actors.js';
import {activityText, newRewards, ATTRIBUTES, rewardTexts, reportIsFresh, reportStorageKey, ExpeditionHud, prologueView, shopSections, debugText} from '../src/dimensional_sim/world/browser/hud.js';
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
test('two perpendicular held keys move diagonally; pause and reset release all input',()=>{
  const input=new Controls();
  input.press('w','north'); input.press('d','east');input.press('w','north');
  assert.equal(input.payload(false,[]).move,'northeast');
  input.release('d');assert.equal(input.payload(false,[]).move,'north');
  input.attack(true);
  assert.deepEqual(input.payload(true,['x']),{move:null,attack:false,paused:true,known:['x']});
  input.reset();assert.deepEqual(input.payload(false,[]),{move:null,attack:false,paused:false,known:[]});
});
test('movement stick changes cardinal direction and stops at its dead zone',()=>{
  assert.equal(stickDirection(4, 3), null);
  assert.equal(stickDirection(27, 9), 'east');
  assert.equal(stickDirection(-22, 8), 'west');
  assert.equal(stickDirection(8, -28), 'north');
  assert.equal(stickDirection(-7, 29), 'south');
  const input = new Controls();
  input.steer('stick', 'north');
  assert.equal(input.payload(false, []).move, 'north');
  input.steer('stick', 'east');
  assert.equal(input.payload(false, []).move, 'east');
  input.steer('stick', null);
  assert.equal(input.payload(false, []).move, null);
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

test('enemy sprites are well-formed rectangles with defined color roles',()=>{
  for(const s of [ENEMY]) {
    assert.equal(s.paint.length,s.glyph.length);
    const w=s.paint[0].length;
    s.paint.forEach((row,r)=>{assert.equal(row.length,w);assert.equal(s.glyph[r].length,w);
      for(const role of row) assert.ok(role===' ' || ROLE[role],'unknown role '+role);});
  }
});
test('actors are large enough to read against terrain (size regression guard)',()=>{
  const player=pixelPlayerFrame(false);
  assert.ok(player.width>=TILE_W && player.height>=TILE_H,`player ${player.width}x${player.height}`);
  const enemy=spriteSize(ENEMY);
  assert.ok(enemy.width>=TILE_W*1.5 && enemy.height>=TILE_H*1.5);
  const filled=ENEMY.paint.join('').replace(/ /g,'').length;
  assert.ok(filled>=40,'enemy silhouette must be solid, not sparse glyphs');
});
test('west view mirrors east; walking changes legs; attack poses differ by phase',()=>{
  const mirrored=pixelPlayerArt(pose('east')).rects.map(([c,x,y,w,h])=>[c,16-x-w,y,w,h]);
  assert.deepEqual(pixelPlayerArt(pose('west')).rects,mirrored);
  assert.notDeepEqual(pixelPlayerArt(pose('south','walk',0)),pixelPlayerArt(pose('south','walk',130)));
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
  assert.ok(pixelPlayerFrame(true).height<pixelPlayerFrame(false).height,'working poses crouch');
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
  assert.notEqual(reportStorageKey('42',{life:0,seq:0}),reportStorageKey('43',{life:0,seq:0}),
    'a new seeded world must show its own opening');
  const base={expedition:{mode:'home',goal:null,activity:null,control:'auto',depth:2}};
  assert.match(activityText(base),/anchor camp/);
  assert.match(activityText({expedition:{...base.expedition,mode:'rest',activity:{kind:'rest',name:'Resting',progress:500}}}),/Resting at the anchor camp - 50%/);
  for(const [id,s] of Object.entries(CAMP)) s.paint.forEach((row,r)=>{assert.equal(row.length,s.paint[0].length,id);assert.equal(s.glyph[r].length,row.length,id);});
  assert.equal(POSE.rest,'sit');
});
test('food slot visibly and accessibly recovers during its shared cooldown',()=>{
  const values=new Map(), classes=new Map(), attrs=new Map();
  const slot={dataset:{name:'Wild berries',count:'3'},
    style:{setProperty:(key,value)=>values.set(key,value)},
    classList:{toggle:(key,value)=>classes.set(key,value)},
    setAttribute:(key,value)=>attrs.set(key,value)};
  const hud=new ExpeditionHud({getElementById:()=>({querySelectorAll:()=>[slot]})});
  const states=[];
  for(const ms of [15000,7500,0]) {
    hud.updateFoodCooldown({vitals:{food_cooldown_ms:ms,food_cooldown_total_ms:15000}});
    states.push([Number(values.get('--food-brightness')),values.get('--food-fill'),classes.get('on-cooldown'),attrs.get('aria-label')]);
  }
  assert.ok(states[0][0]<states[1][0] && states[1][0]<states[2][0]);
  assert.deepEqual(states.map(row=>row[1]),['0.0%','50.0%','100.0%']);
  assert.deepEqual(states.map(row=>row[2]),[true,true,false]);
  assert.match(states[0][3],/15 seconds/);
  assert.match(states[2][3],/Food ready$/);
});

test('prologue: dark awakening with memories, eyes open, then the old man speaks',()=>{
  const memories=['a','b','c','d'];
  const dark=progress=>prologueView({stage:'awaken',progress,lines:memories,elder:{x:1,y:0}});
  assert.equal(dark(0).dark,true); assert.equal(dark(0).memories,1); assert.equal(dark(0).eyes,0);
  assert.ok(dark(400).memories>dark(0).memories && dark(799).memories===4,'memories surface one by one');
  assert.ok(dark(910).eyes>0 && dark(910).eyes<1 && dark(1000).eyes===1,'eyes open at the end');
  const elder=['Why... I don\'t believe it.','The gods saved you.'];
  const talk=progress=>prologueView({stage:'listen',progress,lines:elder});
  assert.equal(talk(0).text,''); assert.equal(talk(0).line,0);
  assert.equal(talk(400).text,elder[0],'a line finishes typing before its turn ends');
  assert.equal(talk(500).line,1); assert.ok(talk(600).text.length<elder[1].length);
  assert.equal(talk(1000).text,elder[1]);
  assert.equal(prologueView(null).stage,null);
  const ex=(stage,progress)=>({expedition:{control:'auto',prologue:{stage,progress,lines:[]},activity:{name:'x',kind:stage,progress}}});
  assert.equal(activityText(ex('awaken',420)),'Wake up - 42%');
  assert.equal(activityText(ex('stand_up',990)),'Stand up - 99%');
  assert.equal(activityText(ex('listen',10)),'Listening to the old man');
  ELDER.paint.forEach((row,r)=>{assert.equal(row.length,ELDER.paint[0].length);assert.equal(ELDER.glyph[r].length,row.length);});
  for(const role of new Set(ELDER.paint.join('').replaceAll(' ',''))) assert.ok('hrswogb'.includes(role),role);
});
test('timed prayer is visible and its completed blessing has a clear source',()=>{
  assert.equal(POSE.pray,'kneel');
  assert.equal(POSE.think,'sit'); assert.equal(POSE.contemplate,'sit');
  const prayer={type:'blessing',items:[],text:'You finished a prayer',blessing:1};
  assert.deepEqual(rewardTexts(prayer).map(r=>r.text),['+1 blessing','Prayer completed']);
  assert.equal(activityText({expedition:{control:'auto',activity:{name:'Praying to the gods',kind:'pray',progress:300}}}),
    'Praying to the gods - 30%');
});

test('crouching hands start at the torso, never the head, in every direction',async()=>{
  const {workingHands}=await import('../src/dimensional_sim/world/browser/actors.js');
  const x=60, y=70, near={south:[2,3],north:[2,1],east:[3,2],west:[1,2]};
  for(const [dir,[tx,ty]] of Object.entries(near)) {
    const hands=workingHands({x:tx,y:ty},'south',x,y,300);
    assert.equal(hands.behind,dir==='north',dir);
    for(const [sx,sy,hx] of hands.arms) {
      assert.ok(sy>=y-10,`${dir}: shoulder below the head`);
      if(dir==='east') assert.ok(hx>x); if(dir==='west') assert.ok(hx<x);
    }
  }
});

// Pixel-player acceptance checks (docs: one silhouette, every fill pixel enclosed by
// OUTLINE except the ground row, no 1px fill slivers, constant frame and feet row).
const actorsModule=await import('../src/dimensional_sim/world/browser/actors.js');
const {pixelPlayerArt,pixelPlayerPose,paintPixelPlayer,pixelPlayerFrame,PIXEL,OUTLINE,AMBUSH,drawAmbushSite,drawPlayer}=actorsModule;
function artGrid(art){
  const g=Array.from({length:art.height},()=>Array(art.width).fill(null));
  for(const [color,x,y,w,h] of art.rects){
    assert.ok(x>=0&&y>=0&&x+w<=art.width&&y+h<=art.height,`rect ${[x,y,w,h]} inside the frame`);
    for(let j=y;j<y+h;j++)for(let i=x;i<x+w;i++)g[j][i]=color;
  }
  return g;
}
const N4=[[1,0],[-1,0],[0,1],[0,-1]];
function components(g,pred){
  const at=(x,y)=>(y>=0&&y<g.length&&x>=0&&x<g[0].length)?g[y][x]:null;
  const seen=new Set(),out=[],W=g[0].length;
  for(let y=0;y<g.length;y++)for(let x=0;x<W;x++)if(pred(at(x,y))&&!seen.has(y*W+x)){
    const q=[[x,y]],cells=[];seen.add(y*W+x);
    while(q.length){const [a,b]=q.pop();cells.push([a,b]);
      for(const [dx,dy] of N4){const k=(b+dy)*W+a+dx;if(pred(at(a+dx,b+dy))&&!seen.has(k)){seen.add(k);q.push([a+dx,b+dy]);}}}
    out.push(cells);
  }
  return out;
}
const PIXEL_FRAMES=[];
for(const facing of ['south','north','east','west']){
  for(const [animation,ms] of [['idle',0],['idle',900],['walk',0],['walk',130],['walk',260],['walk',390],['run',90],['run',270]])
    PIXEL_FRAMES.push({player:pose(facing,animation,ms),compact:false});
  PIXEL_FRAMES.push({player:pose(facing),compact:true});
}
for(const {player,compact} of PIXEL_FRAMES) test(`pixel player ${player.facing} ${compact?'crouch':player.animation+' '+player.animation_ms} has no detached pixels`,()=>{
  const art=pixelPlayerArt(player,{compact}),g=artGrid(art);
  assert.equal(art.width,16); assert.equal(art.height,compact?13:20);
  const frame=pixelPlayerFrame(compact);
  assert.deepEqual(frame,{width:32,height:compact?26:40});
  assert.ok(art.height*PIXEL<=frame.height && art.width*PIXEL===frame.width);
  assert.equal(components(g,c=>c!==null).length,1,'silhouette is one 4-connected piece');
  const at=(x,y)=>(y>=0&&y<g.length&&x>=0&&x<16)?g[y][x]:null;
  const naked=[];
  for(let y=0;y<art.height-1;y++)for(let x=0;x<16;x++)
    if(g[y][x]&&g[y][x]!==OUTLINE&&N4.some(([dx,dy])=>!at(x+dx,y+dy)))naked.push([x,y]);
  assert.deepEqual(naked,[],'every fill pixel is enclosed by OUTLINE (ground row exempt)');
  for(const cells of components(g,c=>c&&c!==OUTLINE)){
    const xs=cells.map(c=>c[0]),ys=cells.map(c=>c[1]);
    assert.ok(cells.length>=2&&Math.max(...xs)>Math.min(...xs)&&Math.max(...ys)>Math.min(...ys),`no 1px fill sliver at ${cells[0]}`);
  }
  assert.ok(g.at(-1).some(Boolean),'feet always on the bottom row');
  assert.ok(!art.rects.some(([c])=>c==='#241c1b'),'the pixel player uses the shared OUTLINE colour');
});
test('pixel player paints whole world pixels with feet on the frame bottom and a stable pose key',()=>{
  for(const compact of [false,true]) for(const facing of ['south','east','west','north']){
    const rects=[];let fill=null;
    const ctx={set fillStyle(v){fill=v;},fillRect:(x,y,w,h)=>rects.push([fill,x,y,w,h])};
    paintPixelPlayer(ctx,pose(facing,'walk',130),10,20,{compact});
    for(const [,x,y,w,h] of rects) assert.ok([x,y,w,h].every(Number.isInteger)&&(x-10)%PIXEL===0&&w%PIXEL===0);
    assert.equal(Math.max(...rects.map(([,,y,,h])=>y+h)),20+pixelPlayerFrame(compact).height,'feet row');
  }
  assert.deepEqual(pixelPlayerPose(pose('east','walk',0)),pixelPlayerPose(pose('east','walk',260)));
  assert.notDeepEqual(pixelPlayerPose(pose('east','walk',130)),pixelPlayerPose(pose('east','walk',390)));
});
function recordingCtx(){
  const calls=[];
  const ctx=new Proxy({},{get:(_,k)=>k==='calls'?calls:(...a)=>{calls.push([k,...a]);
    return k==='createLinearGradient'||k==='createRadialGradient'?{addColorStop(){}}:undefined;},set:()=>true});
  return ctx;
}
test('crouch is a real frame: no squash scaling, same API, hands on the 2px grid',()=>{
  for(const facing of ['south','north','east','west']) for(const [ax,ay] of [[2,3],[2,1],[3,2],[1,2]]){
    const ctx=recordingCtx(),x=60,y=70;
    const box=drawPlayer(ctx,pose(facing),x,y,null,{activity:{kind:'forage',x:ax,y:ay,progress:500},clock:300});
    assert.deepEqual(box,{left:x-16,top:y+12-26,width:32,height:26});
    assert.ok(!ctx.calls.some(([k,sx,sy])=>k==='scale'&&sx!==sy),'no non-uniform squash');
    const fills=ctx.calls.filter(([k])=>k==='fillRect').map(c=>c.slice(1));
    assert.ok(fills.every(r=>r.every(Number.isInteger)),'whole pixels only');
  }
  const rects=[];let fill=null;
  const rec=new Proxy({},{get:(_,k)=>k==='fillRect'?(...a)=>rects.push([fill,...a]):()=>({addColorStop(){}}),set:(_,k,v)=>{if(k==='fillStyle')fill=v;return true;}});
  drawPlayer(rec,pose('south'),61,70,null,{activity:{kind:'forage',x:2,y:3,progress:0},clock:500});
  const sleeves=rects.filter(([c,,,w])=>c===ROLE.c.fill&&w===PIXEL);
  assert.ok(sleeves.length>0,'working arms drawn');
  for(const [,x,y] of sleeves) assert.ok(x%PIXEL===0&&y%PIXEL===0,`sleeve cell ${x},${y} on the art grid`);
});
test('ambush wagons are outlined cell sprites with no free-drawn geometry',()=>{
  for(const [id,s] of Object.entries(AMBUSH)){
    assert.equal(s.paint.length,s.glyph.length,id);
    s.paint.forEach((row,r)=>{assert.equal(row.length,s.paint[0].length,id);assert.equal(s.glyph[r].length,row.length,id);});
    assert.ok(s.paint[0].length<=24&&s.paint.length<=8,`${id} within 24x8 cells`);
  }
  for(const id of ['crate','crateDark']) assert.deepEqual([AMBUSH[id].paint[0].length,AMBUSH[id].paint.length],[4,2]);
  const ctx=recordingCtx();drawAmbushSite(ctx,100.4,200.6);
  const kinds=new Set(ctx.calls.map(c=>c[0]));
  for(const banned of ['arc','ellipse','lineTo','stroke','strokeRect','rotate','createLinearGradient','createRadialGradient'])
    assert.ok(!kinds.has(banned),banned);
  const fills=ctx.calls.filter(([k])=>k==='fillRect');
  assert.ok(fills.length>100&&fills.every(c=>c.slice(1).every(Number.isInteger)));
  const xs=fills.map(c=>c[1]-100),ys=fills.map(c=>c[2]-201);
  assert.ok(Math.min(...xs)>=-160&&Math.max(...xs)<=180&&Math.min(...ys)>=-60&&Math.max(...ys)<=50,'footprint unchanged');
});

test('anchor shop groups server rows and the debug overlay explains buckets',()=>{
  const shop=[{kind:'unlock',id:'climbing',owned:false,available:true},{kind:'unlock',id:'snares',owned:true,available:false},
    {kind:'boon',id:'iron_skin',owned:false,available:false},{kind:'mastery',id:'bramble_berries',owned:false,available:false}];
  const sections=shopSections(shop);
  assert.deepEqual(sections.map(s=>s.kind),['unlock','boon','mastery']);
  assert.deepEqual(sections[0].rows.map(r=>r.id),['climbing'],'owned unlocks are hidden');
  assert.deepEqual(shopSections(null),[]);
  const text=debugText({world_seed:'7',life:2,chunk:'forest:0:0',region:'old_road',currencies:{dust:1,ash:2,blessing:3},
    boon:null,unlocked:[],spot_bucket:[{id:'bramble_berries',weight:13,share_permille:224}],self_bucket:[],need:null,
    windows:[{id:'bramble_boar',active:1,limit:1,spawned:2}],drought:{food:1},pity_after:{food:5},stats:{chunks:9},
    why_not:[{id:'gnarled_tree',reasons:["locked: needs unlock 'Climbing' (15 dust)"]}],
    screening:[{chunk:'forest:1:0',action:'bramble_boar',result:'rejected: window full (1/1 at once)'}]});
  for(const needle of ['seed 7','bramble_berries 13 (22.4%)','bramble_boar 1/1','food 1/5','gnarled_tree: locked','window full'])
    assert.ok(text.includes(needle),needle);
  assert.match(activityText({expedition:{control:'auto',activity:{kind:'craft',name:'Carve a walking staff',progress:500}}}),/^Carve a walking staff - 50%/);
});

test('stick and keys move in eight directions', async () => {
  const {stickDirection: stick, combineHeld, Controls: C} = await import('../src/dimensional_sim/world/browser/view.js');
  assert.equal(stick(20, -20), 'northeast');
  assert.equal(stick(-20, 20), 'southwest');
  assert.equal(stick(30, 4), 'east');
  assert.equal(stick(3, 3), null);
  assert.equal(combineHeld(['east', 'north']), 'northeast');
  assert.equal(combineHeld(['west', 'east']), 'west', 'opposite keys: newest wins');
  const input = new C();
  input.press('KeyW', 'north'); input.press('KeyD', 'east');
  assert.equal(input.payload(false, []).move, 'northeast');
  input.release('KeyW');
  assert.equal(input.payload(false, []).move, 'east');
});
