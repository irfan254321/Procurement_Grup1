import * as THREE from './three/three.module.min.js';
import {buildRoomStage,roomSeats,showroomPositions,showroomProducts} from './room-stage.mjs';

import {studio} from './studio.mjs';
import {createCharacter} from './character-3d.mjs';
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
      const age=(time-state.started)/1000;
      const moving=age<state.travel&&!lowMotion.matches;
      const amount=moving?Math.max(0,age/state.travel):1;
      root.position.set(range(state.fromX,state.toX,amount),0,range(state.fromY,state.toY,amount));
      root.rotation.y=moving?turn(.65,state.toX,state.toY,state.fromX,state.fromY):state.facing;
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
      const [toX,toY]=job.to??[seat?.x??person.x,seat?.z??person.y];
      if(!existing||state.activity!==activityKey||state.toX!==toX||state.toY!==toY||state.job.kind!==job.kind||replay){
        const enter=(!existing||replay)&&(person.enters||person.called);
        const fromX=enter?person.x:!existing&&seat?toX:replay||!existing?person.x:root.position.x;
        const fromY=enter?7.65:!existing&&seat?toY:replay||!existing?person.y:root.position.z;
        const distance=Math.hypot(toX-fromX,toY-fromY);
        Object.assign(state,{fromX,fromY,toX,toY,started:performance.now(),activity:activityKey,seat,
          travel:distance>.07?Math.min(2.2,.6+distance*.38):0,facing:seat?.facing??turn(.65,toX,toY,fromX,fromY),job});
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
