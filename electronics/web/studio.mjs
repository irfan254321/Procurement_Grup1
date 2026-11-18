import * as THREE from './three/three.module.min.js';

export function softBox(w,h,d,radius=.1){
  const r=Math.min(radius,w/2,h/2,d/2);
  const shape=new THREE.BoxGeometry(w,h,d,6,6,6);
  const pos=shape.attributes.position;
  const center=new THREE.Vector3(), corner=new THREE.Vector3();
  const x=w/2-r,y=h/2-r,z=d/2-r;
  for(let i=0;i<pos.count;i++){
    corner.fromBufferAttribute(pos,i);
    center.set(THREE.MathUtils.clamp(corner.x,-x,x),THREE.MathUtils.clamp(corner.y,-y,y),THREE.MathUtils.clamp(corner.z,-z,z));
    corner.sub(center).normalize();
    pos.setXYZ(i,center.x+corner.x*r,center.y+corner.y*r,center.z+corner.z*r);
    shape.attributes.normal.setXYZ(i,corner.x,corner.y,corner.z);
  }
  return shape;
}

export function studio(renderer,scene){
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.24;
  renderer.shadowMap.enabled=true;
  renderer.shadowMap.type=THREE.PCFShadowMap;
  scene.add(new THREE.HemisphereLight('#fff3dc','#819dc2',2.1));
  const key=new THREE.DirectionalLight('#ffe1bb',3.3);
  key.position.set(-6,17,9);
  key.castShadow=true;
  key.target.position.set(6,0,4);
  Object.assign(key.shadow.camera,{left:-12,right:12,top:12,bottom:-12,near:.5,far:40});
  key.shadow.mapSize.set(1024,1024);
  key.shadow.normalBias=.035;
  scene.add(key,key.target);
  const fill=new THREE.DirectionalLight('#b7dcff',1.45);
  fill.position.set(10,5,-8);
  scene.add(fill);
}

export function makeStudioActor(index,customer=false,role='',id=''){
  const root=new THREE.Group(),body=new THREE.Group(),head=new THREE.Group();
  root.add(body);body.add(head);
  head.position.y=.98;
  const colors=['#128c8c','#775ac4','#e67656','#458253','#e6a040','#3e75ae'];
  const skin=['#d29374','#a9654c','#f1bc92','#88513d'][index%4];
  const hair=['#302839','#503321','#211d28'][index%3], shirt=colors[index%6];
  function mesh(parent,geometry,color,x,y,z){
    const material=new THREE.MeshStandardMaterial({color,roughness:.66});
    const model=new THREE.Mesh(geometry,material);
    model.position.set(x,y,z);model.castShadow=true;parent.add(model);
    return model;
  }
  function oval(parent,color,x,y,z,sx,sy,sz){
    const model=mesh(parent,new THREE.SphereGeometry(1,16,10),color,x,y,z);
    model.scale.set(sx,sy,sz);return model;
  }
  function box(parent,color,x,y,z,w,h,d){
    return mesh(parent,softBox(w,h,d,.05),color,x,y,z);
  }
  const logistics=!customer&&(role==='stock'||role==='vendor'&&id==='staff-1');
  const jacket=logistics?'#27586d':['#27445b','#43557a','#48576a','#394b65'][index%4];
  oval(body,customer?shirt:jacket,0,.65,0,.21,.24,.145);
  if(!customer){
    if(logistics){
      box(body,'#75b6b5',0,.62,.134,.28,.05,.035);
      box(body,'#d4e6de',-.082,.74,.137,.081,.045,.025);
      box(head,'#e6b462',0,.16,-.01,.38,.11,.34);
      box(head,'#c49250',0,.12,.17,.35,.042,.17);
    }else{
      box(body,'#fff4e2',0,.744,.126,.139,.198,.052);
      for(const sign of [-1,1]){
        box(body,'#e7edf4',sign*.045,.797,.163,.091,.064,.024).rotation.z=sign*.45;
        box(body,'#7590a1',sign*.105,.744,.147,.045,.158,.028).rotation.z=sign*.34;
      }
      if(index%2===0){
        box(body,'#ad4e47',0,.711,.157,.042,.135,.022);
        box(body,'#c36753',0,.784,.158,.056,.038,.027).rotation.z=.25;
      }else{
        box(body,'#75b7af',.084,.761,.168,.018,.093,.012).rotation.z=.28;
        box(body,'#f2e6c5',.083,.704,.167,.062,.067,.017);
      }
    }
  }
  oval(head,skin,0,0,0,.199,.205,.167);
  oval(head,hair,0,.105,-.044,.207,.131,.164);
  oval(head,hair,-.083,.12,.055,.117,.082,.129).rotation.z=.28;
  for(const sign of [-1,1]){
    oval(head,skin,sign*.195,-.013,0,.042,.059,.039);
    oval(head,'#fff9ef',sign*.073,.012,.146,.055,.065,.03);
    oval(head,'#3b5667',sign*.073+.009,.01,.172,.027,.037,.012);
    oval(head,'#ffffff',sign*.073+.001,.026,.182,.009,.012,.004);
    oval(head,hair,sign*.073,.092,.135,.061,.014,.014).rotation.z=sign*.12;
  }
  oval(head,skin,0,-.038,.163,.04,.04,.038);
  const smile=new THREE.QuadraticBezierCurve3(new THREE.Vector3(-.048,-.085,.151),new THREE.Vector3(0,-.128,.156),new THREE.Vector3(.048,-.085,.151));
  mesh(head,new THREE.TubeGeometry(smile,8,.009,6,false),'#964b4e',0,0,0);
  if(customer)box(body,'#e6b366',0,.66,-.145,.25,.3,.12);
  function limb(x,y,arm){
    const pivot=new THREE.Group();pivot.position.set(x,y,0);body.add(pivot);
    oval(pivot,arm?(customer?shirt:jacket):'#30465d',0,-.11,0,arm?.067:.075,arm?.17:.155,.074);
    if(arm){
      if(!customer&&!logistics)box(pivot,'#f5ecdd',0,-.198,.006,.105,.042,.109);
      oval(pivot,skin,0,-.24,.015,.062,.072,.061);
    }
    else box(pivot,'#273b51',0,-.29,.042,.16,.105,.24);
    return pivot;
  }
  const arms=[limb(-.22,.75,true),limb(.22,.75,true)];
  const legs=[limb(-.093,.345,false),limb(.093,.345,false)];
  const prop=new THREE.Group();prop.position.set(0,.58,.34);body.add(prop);
  const boxProp=box(prop,'#e4a467',0,0,0,.31,.24,.25);
  box(boxProp,'#ffddb0',0,.118,0,.048,.012,.253);
  const paper=box(prop,'#fff3d3',0,0,0,.27,.035,.2);
  return {root,body,head,arms,legs,prop,box:boxProp,paper};
}

export function disposeStudioActor(actor){
  actor.root.traverse(node=>{
    if(node.isMesh){node.geometry.dispose();node.material.dispose()}
  });
  actor.root.removeFromParent();
}
