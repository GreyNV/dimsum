/** The minimap: discovered chunks, their terrain, spots, enemies and the avatar. */
import {terrainColor} from './art.js';

const MAP_W = 180, MAP_H = 130;

/** Saved tile discovery is authoritative in both map views. */
export function visibleAt(fog, x, y, width, height) {
  const cx=Math.floor(x/width), cy=Math.floor(y/height);
  return fog?.[`${cx}:${cy}`]?.[y-cy*height]?.[x-cx*width] === '1';
}

/** Paint the minimap for snapshot `state` into the 2D context `map`. */
export function drawMinimap(map, state, chunks, dpr) {
  map.setTransform(dpr,0,0,dpr,0,0);
  map.fillStyle = '#0b110b'; map.fillRect(0,0,MAP_W,MAP_H);
  const entries = state.minimap;
  if (!entries.length) return;
  const minX = Math.min(...entries.map(p=>p.x)), maxX = Math.max(...entries.map(p=>p.x));
  const minY = Math.min(...entries.map(p=>p.y)), maxY = Math.max(...entries.map(p=>p.y));
  const spanX = (maxX-minX+1) * state.chunk_width, spanY = (maxY-minY+1) * state.chunk_height;
  const scale = Math.min((MAP_W-6)/spanX,(MAP_H-6)/spanY), left=(MAP_W-spanX*scale)/2, top=(MAP_H-spanY*scale)/2;
  const fog = state.fog || {};
  const coords = new Map([...chunks.values()].map(c=>[c.x+':'+c.y,c]));
  for (const entry of entries) {
    const x=left+(entry.x-minX)*state.chunk_width*scale, y=top+(entry.y-minY)*state.chunk_height*scale;
    const w=state.chunk_width*scale, h=state.chunk_height*scale;
    map.fillStyle = '#10180f';
    map.fillRect(x,y,w,h);
    const chunk=coords.get(entry.x+':'+entry.y);
    const rows=fog[`${entry.x}:${entry.y}`];
    if (rows) {
      for (let ry=0;ry<state.chunk_height;ry++) for(let rx=0;rx<state.chunk_width;rx++) {
        if (rows[ry]?.[rx] !== '1') continue;
        map.fillStyle=chunk ? terrainColor(chunk.tiles[ry][rx]) : '#405031';
        map.fillRect(x+rx*scale,y+ry*scale,Math.max(.7,scale),Math.max(.7,scale));
      }
    } else {
      map.fillStyle='#26301f';
      for(let py=y+3;py<y+h;py+=5) for(let px=x+3;px<x+w;px+=5) map.fillRect(px,py,.7,.7);
    }
  }
  const px=left+(state.player.x-minX*state.chunk_width+.5)*scale;
  const py=top+(state.player.y-minY*state.chunk_height+.5)*scale;
  const mark=(gx,gy,color,r)=>{
    const mx=left+(gx-minX*state.chunk_width+.5)*scale, my=top+(gy-minY*state.chunk_height+.5)*scale;
    map.fillStyle='#070a06'; map.fillRect(mx-r-.6,my-r-.6,r*2+1.2,r*2+1.2);
    map.fillStyle=color; map.fillRect(mx-r,my-r,r*2,r*2);
  };
  for(const spot of state.spots||[]) if(visibleAt(fog, spot.x, spot.y, state.chunk_width, state.chunk_height))
    mark(spot.x,spot.y,'#e2c066',1.1);
  // Enemies: hunters always show (pulsing ring), fleeing ones fade; others only where explored.
  const pulse = 1.6 + (Math.floor(performance.now() / 250) % 2) * .6;
  for(const t of state.targets) {
    if (t.hp <= 0) continue;
    if (t.hunting === 'hunt') {
      mark(t.x,t.y,'#ff5a46',1.4);
      const mx=left+(t.x-minX*state.chunk_width+.5)*scale, my=top+(t.y-minY*state.chunk_height+.5)*scale;
      map.strokeStyle='#ff5a46'; map.lineWidth=.8; map.strokeRect(mx-pulse-1.4,my-pulse-1.4,(pulse+1.4)*2,(pulse+1.4)*2);
    } else if (t.hunting === 'flee') mark(t.x,t.y,'#8a5a50',1);
    else if (visibleAt(fog, t.x, t.y, state.chunk_width, state.chunk_height)) mark(t.x,t.y,'#e0604f',1.1);
  }
  // The anchor camp (and this life's campfire), kept on the map's edge when outside it.
  const place=(gx,gy,color)=>{
    const mx=Math.max(3,Math.min(MAP_W-3,left+(gx-minX*state.chunk_width+.5)*scale));
    const my=Math.max(3,Math.min(MAP_H-3,top+(gy-minY*state.chunk_height+.5)*scale));
    map.fillStyle='#070a06'; map.beginPath(); map.moveTo(mx,my-4); map.lineTo(mx+4,my); map.lineTo(mx,my+4); map.lineTo(mx-4,my); map.closePath(); map.fill();
    map.fillStyle=color; map.beginPath(); map.moveTo(mx,my-3); map.lineTo(mx+3,my); map.lineTo(mx,my+3); map.lineTo(mx-3,my); map.closePath(); map.fill();
  };
  const ex=state.expedition;
  if(ex?.campfire) place(ex.campfire.x,ex.campfire.y,'#ff9a4a');
  if(ex?.anchor) place(ex.anchor.x,ex.anchor.y,'#f1d38a');
  map.fillStyle='#fff1bc'; map.fillRect(px-1.8,py-1.8,3.6,3.6);
  map.strokeStyle='#ffe6a0'; map.lineWidth=.7; map.strokeRect(px-3.5,py-3.5,7,7);
}
