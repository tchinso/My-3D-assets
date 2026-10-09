import assert from 'node:assert/strict';
import {insideRect, floorAt, blocked, moveWithCollisions} from '../map-viewer/navigation.js';

assert.equal(insideRect(0,1.5,{x:0,z:0,w:4,d:1,rot:Math.PI/2}),true,'rotated walls use local dimensions');
assert.equal(insideRect(1.5,0,{x:0,z:0,w:4,d:1,rot:Math.PI/2}),false);
const surfaces=[{x:0,z:0,w:10,d:10,y:0},{x:0,z:0,w:2,d:2,y:3}];
assert.equal(floorAt(surfaces,0,0,0),0,'a floor above the head cannot teleport a traveler');
assert.equal(floorAt(surfaces,0,0,3),3);
assert.equal(floorAt(surfaces,0,0),3,'initial spawn supports upper platforms');
assert.equal(blocked([{x:0,z:0,w:3,d:3,y:-2,h:2}],0,0,.1),false,'water/structure beneath a bridge does not block it');
assert.equal(blocked([{x:0,z:0,w:3,d:3,y:0,h:3}],0,0,0),true);
const world={width:20,depth:20,surfaces:[{x:0,z:0,w:20,d:20,y:0}],colliders:[{x:0,z:0,w:.1,d:8,y:0,h:3}]};
const p={x:-2,y:0,z:0};moveWithCollisions(world,p,8,0);assert.ok(p.x<-.2,'high movement speed cannot tunnel through thin walls');
moveWithCollisions(world,p,1,2);assert.ok(p.z>1.9,'blocked motion can slide along a wall');
const stairs={width:10,depth:10,colliders:[],surfaces:[{x:0,z:0,w:10,d:10,y:0},...Array.from({length:5},(_,i)=>({x:0,z:1.8-i*.4,w:2,d:.4,y:(i+1)*.2}))]};
const s={x:0,y:0,z:2.1};moveWithCollisions(stairs,s,0,-2);assert.ok(s.y>=.8,'registered stair treads increase foot elevation');
const gap={width:10,depth:10,colliders:[],surfaces:[{x:-2,z:0,w:2,d:4,y:0},{x:2,z:0,w:2,d:4,y:0}]};
const g={x:-2,y:0,z:0};moveWithCollisions(gap,g,4,0);assert.ok(g.x<=-1,'unregistered gaps cannot be walked across');
console.log('PASS: rotation, stacked floors, bridge clearance, thin obstacles, wall sliding, stairs and gaps');
