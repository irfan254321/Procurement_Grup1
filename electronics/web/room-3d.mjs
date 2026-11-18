import * as THREE from './three/three.module.min.js';
import {buildRoomStage,showroomPositions} from './room-stage.mjs';

import {studio,makeStudioActor,disposeStudioActor} from './studio.mjs';
import {loadPolyAssets} from './poly-assets.mjs';

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
  let stage, stageKey, roomIdentity, mount, frame=0;
  const range=(a,b,t)=>a+(b-a)*t;

  function turn(facing,targetX,targetZ,currentX,currentZ){
    return Math.hypot(targetX-currentX,targetZ-currentZ)>.025?
      Math.atan2(targetX-currentX,targetZ-currentZ):facing;
  }

  function draw(time){
    frame=0;
    if(!mount?.isConnected||!mount.getClientRects().length)return;
    for(const state of actors.values()){
      const {root,body,head,arms,legs,prop,box,paper,person,job}=state;
      const age=(time-state.started)/1000;
      const moving=age<state.travel&&!lowMotion.matches;
      const amount=moving?Math.max(0,age/state.travel):1;
      root.position.set(range(state.fromX,state.toX,amount),0,range(state.fromY,state.toY,amount));
      root.rotation.y=moving?turn(.65,state.toX,state.toY,state.fromX,state.fromY):state.facing;
      const gesture=lowMotion.matches?0:Math.sin(age*(moving?12:4.8));
      body.position.y=moving?Math.abs(gesture)*.054:lowMotion.matches?0:Math.sin(age*1.9)*.013;
      body.rotation.z=moving?0:lowMotion.matches?0:Math.sin(age*1.6)*.025;
      for(const [i,sign] of [[0,1],[1,-1]]){
        legs[i].rotation.x=moving?sign*.54*gesture:0;
        arms[i].rotation.x=moving?sign*.43*gesture:-.06;
      }
      const kind=job.kind;
      head.rotation.y=moving?0:gesture*.16;
      head.rotation.x=kind==='talk'&&!moving?gesture*.12:0;
      const carrying=kind==='carry'&&(moving||age<state.travel+.65);
      if(carrying)arms.forEach(arm=>{arm.rotation.x=-1.21});
      if(!moving&&age<state.travel+2.7&&['type','scan','stamp','talk','mail'].includes(kind)){
        arms[1].rotation.x=-.8-.62*gesture;
        arms[0].rotation.x=kind==='type'?-.95+.21*gesture:-.2;
      }
      prop.visible=carrying||age<state.travel+2.7&&!moving&&['scan','stamp','mail'].includes(kind);
      box.visible=carrying;
      paper.visible=!carrying;
      if(person.pin){
        point.set(root.position.x,1.35+body.position.y,root.position.z).project(camera);
        person.pin.style.left=50+50*point.x+'%';
        person.pin.style.top=50-50*point.y+'%';
      }
    }
    renderer.render(scene,camera);
    frame=requestAnimationFrame(draw);
  }

  function labelProducts(node,role){
    const positions=showroomPositions[role]??[];
    const names=['Laptop','Monitor','Printer'];
    const heights=[1.45,1.78,1.43];
    node.replaceChildren(...positions.map(([x,z],index)=>{
      const label=document.createElement('span');
      label.className='room-product-label';
      label.textContent=names[index];
      point.set(x,heights[index],z).project(camera);
      label.style.left=50+50*point.x+'%';
      label.style.top=50-50*point.y+'%';
      return label;
    }));
  }

  function clearActors(){
    for(const state of actors.values())disposeStudioActor(state);
    actors.clear();
  }

  function update(node,productLabels,key,room,role,people,activityKey,replay=false){
    if(roomIdentity!==key){
      clearActors();
      roomIdentity=key;
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
      labelProducts(productLabels,role);
    }
    if(mount!==node||renderer.domElement.parentElement!==node){
      mount=node;
      node.replaceChildren(renderer.domElement);
    }
    const current=new Set(people.map(person=>person.id));
    for(const [id,state] of actors){
      if(current.has(id))continue;
      disposeStudioActor(state);
      actors.delete(id);
    }
    for(const [index,person] of people.entries()){
      const existing=actors.get(person.id);
      const state=existing??makeStudioActor(index,person.id.startsWith('customer-'),role,person.id);
      if(!existing)scene.add(state.root);
      const job=person.jobMotion??{kind:'idle',label:''};
      if(!existing||state.activity!==activityKey||state.toX!==(job.to?.[0]??person.x)||state.toY!==(job.to?.[1]??person.y)||replay){
        const [toX,toY]=job.to??[person.x,person.y];
        const enter=(!existing||replay)&&(person.enters||person.called);
        const fromX=replay||enter||!existing?person.x:state.root.position.x;
        const fromY=enter?7.65:replay||!existing?person.y:state.root.position.z;
        const distance=Math.hypot(toX-fromX,toY-fromY);
        Object.assign(state,{fromX,fromY,toX,toY,started:performance.now(),activity:activityKey,
          travel:distance>.07?Math.min(2.2,.6+distance*.38):0,facing:turn(.65,toX,toY,fromX,fromY),job});
      }
      state.person=person;
      actors.set(person.id,state);
    }
    if(!frame)frame=requestAnimationFrame(draw);
  }
  return {update, stop(){
    cancelAnimationFrame(frame);
    frame=0;
  }};
}
