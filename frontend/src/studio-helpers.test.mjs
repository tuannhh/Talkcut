import test from 'node:test';
import assert from 'node:assert/strict';
import {wordGroups,focusAt,focusGeometry} from './studio-helpers.mjs';
test('sentence rows preserve word references and pause/speaker boundaries',()=>{const w=[{text:'Xin',start:0,end:.2,speaker:'a'},{text:'chào.',start:.3,end:.6,speaker:'a'},{text:'Câu',start:.7,end:.9,speaker:'a'},{text:'tiếp',start:1,end:1.2,speaker:'b'}];const groups=wordGroups(w);assert.deepEqual(groups.map(g=>g.map(w=>w.text)),[['Xin','chào.'],['Câu'],['tiếp']]);assert.equal(groups[0][0],w[0]);});
test('preview does not drift between speakers before a cut',()=>{const p=[{time:0,x:.8,y:.5,scene:0,mode:'crop'},{time:4,x:.2,y:.5,scene:1,mode:'crop',cut:true}];assert.equal(focusAt(p,3.9).x,.8);assert.equal(focusAt(p,4).x,.2);});
test('preview stays vertical while awaiting focus and for oversized faces',()=>{assert.equal(focusAt([],3).mode,'crop');const p=focusGeometry({width:1920,height:1080},{crop_zoom:1},{mode:'crop',x:.5,face:[.2,.1,.8,.7]});assert.equal(p.mode,'crop');});
test('face fitting matches renderer numerically',()=>{const g=focusGeometry({width:1920,height:1080},{crop_zoom:1},{mode:'crop',x:.78,face:[.69,.12,.85,.35]});assert.equal(g.cw,606);assert.equal(g.ch,1080);assert.equal(g.mode,'crop');assert.ok((g.x*1920-303)/1920<=.69);});

import {editTimedGroup,replaceTimedGroup} from './studio-helpers.mjs';
test('direct sentence editing preserves anchors through replacement insertion deletion',()=>{
 const w=['Tôi','là','người','Việt'].map((text,i)=>({text,start:i,end:i+.5,speaker:'a'}));
 const changed=editTimedGroup(w,'Tôi là một người Việt Nam');
 assert.equal(changed.map(x=>x.text).join(' '),'Tôi là một người Việt Nam');
 assert.ok(changed.every(x=>w.some(old=>old.start===x.start&&old.end===x.end)));
 assert.equal(editTimedGroup(w,'Tôi người Việt').map(x=>x.text).join(' '),'Tôi người Việt');
 assert.deepEqual(editTimedGroup(w,''),[]);
 assert.equal(replaceTimedGroup(w,w.slice(1,3),'là công dân').map(x=>x.text).join(' '),'Tôi là công dân Việt');
});

test('stacked geometry keeps a tight bust crop inside the frame',async()=>{
 const {stackedGeometry}=await import('./studio-helpers.mjs');
 const g=stackedGeometry({width:1920,height:1080},{crop_zoom:1},[.05,.1,.2,.3]);
 assert.ok(g.cw>0&&g.ch>0);
 assert.ok(Math.abs(g.ch/g.cw-8/9)<.02);
 assert.ok(g.x>=g.cw/2/1920&&g.x<=1-g.cw/2/1920);
});
test('stacked window lookup finds the active AI-chosen segment',async()=>{
 const {stackedWindowAt}=await import('./studio-helpers.mjs');
 const segments=[{start:1,end:2},{start:5,end:7}];
 assert.equal(stackedWindowAt(segments,1.5),segments[0]);
 assert.equal(stackedWindowAt(segments,3),null);
 assert.equal(stackedWindowAt(segments,6),segments[1]);
});
test('fixed subject uses explicit source-time positions without interpolation',async()=>{
 const {staticCenter}=await import('./studio-helpers.mjs');
 const s={crop_x:.2,crop_y:.5,crop_locks:[{start:105,end:115,x:.8,y:.3}]};
 assert.deepEqual(staticCenter(s,104.99),{x:.2,y:.5});
 assert.deepEqual(staticCenter(s,105),{x:.8,y:.3});
 assert.deepEqual(staticCenter(s,114.99),{x:.8,y:.3});
 assert.deepEqual(staticCenter(s,115),{x:.2,y:.5});
});
