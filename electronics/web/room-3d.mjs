import * as THREE from './three/three.module.min.js';
import {buildRoomStage,roomSeats,showroomPositions,showroomProducts} from './room-stage.mjs';

import {studio} from './studio.mjs';
import {createCharacter} from './character-3d.mjs';
import {loadPolyAssets} from './poly-assets.mjs';

export const roomEntrance = [10.25, 8.18];

export const roomWalkClearance=.2;
const inside=(point,box)=>point[0]>box.minX&&point[0]<box.maxX&&point[1]>box.minZ&&point[1]<box.maxZ;
const padded=box=>({...box,minX:box.minX-roomWalkClearance,maxX:box.maxX+roomWalkClearance,
  minZ:box.minZ-roomWalkClearance,maxZ:box.maxZ+roomWalkClearance});
const inRoom=point=>point[0]>=.22&&point[0]<=10.78&&point[1]>=.22&&point[1]<=8.18;

export function resolveRoomPoint(point,obstacles){
  const blockers=obstacles.filter(box=>box.kind!=='chair'||!inside(point,box)).map(padded);
  const blocked=candidate=>!inRoom(candidate)||blockers.some(box=>inside(candidate,box));
  if(!blocked(point))return point.slice();
  const candidates=[];
  for(const box of blockers){
    candidates.push([box.minX-.02,point[1]],[box.maxX+.02,point[1]],
      [point[0],box.minZ-.02],[point[0],box.maxZ+.02]);
    for(const x of [box.minX-.02,box.maxX+.02])for(const z of [box.minZ-.02,box.maxZ+.02])candidates.push([x,z]);
  }
  candidates.push([Math.min(10.78,Math.max(.22,point[0])),Math.min(8.18,Math.max(.22,point[1]))]);
  return candidates.filter(candidate=>!blocked(candidate)).sort((a,b)=>
    Math.hypot(a[0]-point[0],a[1]-point[1])-Math.hypot(b[0]-point[0],b[1]-point[1]))[0]??null;
}

export function roomSegmentClear(from,to,obstacles){
  for(const box of obstacles){
    let near=0,far=1;
    for(const [axis,min,max] of [[0,box.minX,box.maxX],[1,box.minZ,box.maxZ]]){
      const delta=to[axis]-from[axis];
      if(Math.abs(delta)<1e-10){
        if(from[axis]<=min||from[axis]>=max){near=2;break;}
      }else{
        const a=(min-from[axis])/delta,b=(max-from[axis])/delta;
        near=Math.max(near,Math.min(a,b));
        far=Math.min(far,Math.max(a,b));
      }
    }
    if(near<far&&near<=1&&far>=0)return false;
  }
  return true;
}

export function planRoomPresence(from,to,now,delay=0,obstacles=[]){
  const start=resolveRoomPoint(from,obstacles),goal=resolveRoomPoint(to,obstacles);
  if(!start||!goal)return null;
  // A seated worker may stand up from their own chair or dock at their workstation.
  const blockers=obstacles.filter(box=>box.kind!=='chair'||(!inside(start,box)&&!inside(goal,box))).map(padded);
  const nodes=[start,goal];
  for(const box of blockers)for(const x of [box.minX-.02,box.maxX+.02])for(const z of [box.minZ-.02,box.maxZ+.02]){
    const point=[x,z];
    if(inRoom(point)&&!blockers.some(other=>inside(point,other)))nodes.push(point);
  }
  const distance=nodes.map(()=>Infinity),previous=nodes.map(()=>-1),visited=new Set();
  distance[0]=0;
  for(let pass=0;pass<nodes.length;pass++){
    let current=-1;
    for(let index=0;index<nodes.length;index++){
      if(!visited.has(index)&&(current<0||distance[index]<distance[current]))current=index;
    }
    if(current<0||distance[current]===Infinity)break;
    if(current===1)break;
    visited.add(current);
    for(let next=0;next<nodes.length;next++){
      if(visited.has(next)||!roomSegmentClear(nodes[current],nodes[next],blockers))continue;
      const candidate=distance[current]+Math.hypot(nodes[next][0]-nodes[current][0],nodes[next][1]-nodes[current][1]);
      if(candidate<distance[next]){distance[next]=candidate;previous[next]=current;}
    }
  }
  if(distance[1]===Infinity)return null;
  const points=[];
  for(let index=1;index>=0;index=previous[index])points.unshift(nodes[index]);
  const lengths=points.slice(1).map((point,i)=>Math.hypot(point[0]-points[i][0],point[1]-points[i][1]));
  return {points,lengths,total:distance[1],started:now+delay};
}

export function sampleRoomPresence(motion, now, reducedMotion=false) {
  const distance=reducedMotion?motion.total:Math.max(0,now-motion.started)*.0035;
  if(distance>=motion.total)return {position:motion.points.at(-1),done:true,moving:false};
  let remaining=distance;
  for(let index=0;index<motion.lengths.length;index++){
    const length=motion.lengths[index];
    if(length===0)continue;
    if(remaining<=length){
      const from=motion.points[index],to=motion.points[index+1],t=remaining/length;
      return {position:[from[0]+(to[0]-from[0])*t,from[1]+(to[1]-from[1])*t],
              facing:Math.atan2(to[0]-from[0],to[1]-from[1]),done:false,moving:now>motion.started};
    }
    remaining-=length;
  }
  return {position:motion.points.at(-1),done:true,moving:false};
}

export async function createRoom3D() {
  const assets=await loadPolyAssets(['laptop','monitor','printer','sofa']);
  const renderer = new THREE.WebGLRenderer({antialias:true,alpha:false});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
  renderer.setSize(940,550,false);
  renderer.domElement.className='floor-art floor-webgl';
  renderer.domElement.setAttribute('aria-hidden','true');
  const scene=new THREE.Scene();
  scene.background=new THREE.Color('#daeae9');
  studio(renderer,scene);
  const camera=new THREE.OrthographicCamera(-9.4,9.4,5.5,-5.5,.1,80);
  camera.position.set(15.5,11.8,16);
  camera.lookAt(5.5,.93,4);
  camera.updateMatrixWorld();
  const lowMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
  const actors=new Map();
  const point=new THREE.Vector3();
  let stage, stageKey, roomIdentity, mount, frame=0, wasOffline;
  const workModes={type:'type',scan:'inspect',stamp:'type',talk:'present',mail:'carry',walk:'walk',carry:'carry'};
  const workProps={scan:'paper',mail:'paper',carry:'box'};

  function turn(facing,targetX,targetZ,currentX,currentZ){
    return Math.hypot(targetX-currentX,targetZ-currentZ)>.025?
      Math.atan2(targetX-currentX,targetZ-currentZ):facing;
  }

  function draw(time){
    frame=0;
    if(!mount?.isConnected||!mount.getClientRects().length)return;
    for(const state of actors.values()){
      const {actor,person,job,seat}=state;
      const {root}=actor;
      if(state.presence){
        const pose=sampleRoomPresence(state.presence,time,lowMotion.matches);
        root.position.set(pose.position[0],0,pose.position[1]);
        root.visible=!(pose.done&&state.offline);
        if(pose.facing!==undefined)root.rotation.y=pose.facing;
        actor.animate(pose.moving?'walk':'idle',time/1000,{reducedMotion:lowMotion.matches,seated:false});
        if(person.pin){
          person.pin.hidden=!root.visible;
          actor.head.getWorldPosition(point);
          point.y+=.31;point.project(camera);
          person.pin.style.left=50+50*point.x+'%';
          person.pin.style.top=50-50*point.y+'%';
        }
        if(!pose.done)continue;
        state.presence=null;
        state.fromX=root.position.x;
        state.fromY=root.position.z;
        state.started=time;
        state.route=planRoomPresence([state.fromX,state.fromY],[state.toX,state.toY],time,0,stage.userData.walkObstacles);
        state.travel=(state.route?.total??0)/3.5;
      }
      if(state.offline){
        root.visible=false;
        if(person.pin)person.pin.hidden=true;
        continue;
      }
      root.visible=true;
      if(person.pin)person.pin.hidden=false;
      const age=(time-state.started)/1000;
      const pose=state.route?sampleRoomPresence(state.route,time,lowMotion.matches):null;
      const moving=!!pose?.moving&&!pose.done;
      if(pose)root.position.set(pose.position[0],0,pose.position[1]);
      root.rotation.y=moving?pose.facing:state.facing;
      const working=age<state.travel+2.7;
      const arrival=working&&(person.enters||person.called)&&job.kind==='idle';
      const seated=!!seat&&!moving;
      const deskMode=job.kind==='talk'&&working?'present':job.kind==='scan'&&working?'read':seat?.work;
      const mode=moving?'walk':seated?(person.offline?'sit':deskMode):
        working?(workModes[job.kind]??(arrival?'wave':'idle')):'idle';
      actor.animate(mode,time/1000,{
        reducedMotion:lowMotion.matches,seated,prop:working&&!seated?workProps[job.kind]:undefined,
      });
      if(person.pin){
        actor.head.getWorldPosition(point);
        point.y+=.31;
        point.project(camera);
        person.pin.style.left=50+50*point.x+'%';
        person.pin.style.top=50-50*point.y+'%';
      }
    }
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }

  function labelProducts(node,role,products){
    const positions=showroomPositions[role]??[];
    const heights=[1.45,1.78,1.43];
    node.replaceChildren(...positions.map(([x,z],index)=>{
      const name=showroomProducts[index];
      const stock=products.find(product=>product.name===name)?.units??0;
      const label=document.createElement('span');
      label.className='room-product-label'+(stock>0?'':' sold-out');
      label.textContent=stock>0?name:name+' · Habis';
      point.set(x,stock>0?heights[index]:1,z).project(camera);
      label.style.left=50+50*point.x+'%';
      label.style.top=50-50*point.y+'%';
      return label;
    }));
  }

  function clearActors(){
    for(const {actor} of actors.values()){
      actor.root.removeFromParent();
      actor.dispose();
    }
    actors.clear();
  }

  function update(node,productLabels,key,room,role,people,activityKey,replay=false,products=[],uniform=room.color){
    if(roomIdentity!==key){
      clearActors();
      roomIdentity=key;
      wasOffline=undefined;
    }
    if(stageKey!==room){
      if(stage){
        scene.remove(stage);
        const stageResources=new Set();
        stage.traverse(item=>{
          for(let ancestor=item;ancestor!==stage;ancestor=ancestor.parent){
            if(ancestor.userData.polyAsset)return;
          }
          if(item.geometry)stageResources.add(item.geometry);
          if(item.isInstancedMesh)item.dispose();
          for(const material of Array.isArray(item.material)?item.material:[item.material]){
            if(material)stageResources.add(material);
          }
        });
        stageResources.forEach(resource=>resource.dispose());
      }
      stage=buildRoomStage(THREE,scene,room,role,assets);
      stageKey=room;
    }
    stage.userData.setStock(products);
    labelProducts(productLabels,role,products);
    if(mount!==node||renderer.domElement.parentElement!==node){
      mount=node;
      node.replaceChildren(renderer.domElement);
    }
    const current=new Set(people.map(person=>person.id));
    for(const [id,state] of actors){
      if(current.has(id))continue;
      state.actor.root.removeFromParent();
      state.actor.dispose();
      actors.delete(id);
    }
    for(const [index,person] of people.entries()){
      const existing=actors.get(person.id);
      const offline=person.offline===true;
      if(!existing&&offline){
        if(person.pin)person.pin.hidden=true;
        continue;
      }
      const customer=person.id.startsWith('customer-');
      const state=existing??{actor:createCharacter({role:customer?'customer':role,variant:person.variant??index,
        gender:person.gender,jacket:customer?undefined:uniform,briefcase:false})};
      const {root}=state.actor;
      if(!existing){
        root.scale.setScalar(.72);
        scene.add(root);
      }
      const job=person.jobMotion??{kind:'idle',label:''};
      const seat=!job.to&&job.kind!=='carry'&&job.kind!=='walk'?roomSeats[role]?.[person.id]:null;
      const target=resolveRoomPoint(job.to??[seat?.x??person.x,seat?.z??person.y],stage.userData.walkObstacles);
      if(!target)continue;
      const [toX,toY]=target;
      if(!existing||state.activity!==activityKey||state.toX!==toX||state.toY!==toY||state.job.kind!==job.kind||replay){
        const enter=(!existing||replay)&&(person.enters||person.called);
        const fromX=enter?roomEntrance[0]:existing?root.position.x:toX;
        const fromY=enter?roomEntrance[1]:existing?root.position.z:toY;
        const route=planRoomPresence([fromX,fromY],[toX,toY],performance.now(),0,stage.userData.walkObstacles);
        Object.assign(state,{fromX,fromY,toX,toY,started:performance.now(),activity:activityKey,seat,
          route,travel:(route?.total??0)/3.5,facing:seat?.facing??turn(.65,toX,toY,fromX,fromY),job});
      }
      if((existing&&state.offline!==offline)||(!existing&&wasOffline===true&&!offline)){
        const start=existing&&root.visible?[root.position.x,root.position.z]:roomEntrance;
        const destination=offline?roomEntrance:[toX,toY];
        state.presence=planRoomPresence(start,destination,performance.now(),index*180,stage.userData.walkObstacles);
        root.position.set(start[0],0,start[1]);
        root.visible=true;
      }
      state.offline=offline;
      state.person=person;
      if(person.pin)person.pin.hidden=offline&&!state.presence;
      actors.set(person.id,state);
    }
    wasOffline=people.length>0&&people.every(person=>person.offline);
    if(!frame)frame=requestAnimationFrame(draw);
  }
  return {update, stop(){
    cancelAnimationFrame(frame);
    frame=0;
  }};
}
