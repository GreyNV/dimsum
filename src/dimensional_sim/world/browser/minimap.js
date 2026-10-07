/** The minimap: discovered chunks, their terrain, spots, enemies and the avatar. */
import {terrainColor} from './art.js';

const MAP_W = 180, MAP_H = 130;

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
  const coords = new Map([...chunks.values()].map(c=>[c.x+':'+c.y,c]));
  for (const entry of entries) {
    const x=left+(entry.x-minX)*state.chunk_width*scale, y=top+(entry.y-minY)*state.chunk_height*scale;
    const w=state.chunk_width*scale, h=state.chunk_height*scale;
    map.fillStyle = entry.status === 'unknown' ? '#10180f' : entry.status === 'visited' ? '#405031' : '#26331e';
    map.fillRect(x,y,w,h);
    const chunk=coords.get(entry.x+':'+entry.y);
    if (chunk && entry.status !== 'unknown') {
      map.globalAlpha = entry.status === 'visited' ? .95 : .42;
      for (let ry=0;ry<chunk.height;ry++) for(let rx=0;rx<chunk.width;rx++) {
        map.fillStyle=terrainColor(chunk.tiles[ry][rx]);
        map.fillRect(x+rx*scale,y+ry*scale,Math.max(.7,scale),Math.max(.7,scale));
      }
      map.globalAlpha=1;
    } else if (entry.status === 'unknown') {
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
  for(const spot of state.spots||[]) mark(spot.x,spot.y,'#e2c066',1.1);
  for(const t of state.targets) if(t.hp>0) mark(t.x,t.y,'#e0604f',1.1);
  map.fillStyle='#fff1bc'; map.fillRect(px-1.8,py-1.8,3.6,3.6);
  map.strokeStyle='#ffe6a0'; map.lineWidth=.7; map.strokeRect(px-3.5,py-3.5,7,7);
}
