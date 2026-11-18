import * as THREE from './three/three.module.min.js';
import {GLTFLoader} from './three/GLTFLoader.js';

const loader=new GLTFLoader();
const loading=new Map();
export async function loadPolyAssets(names){
  const models=await Promise.all(names.map(name=>{
    if(!loading.has(name)){
      loading.set(name,loader.loadAsync('/assets/'+name+'.glb').then(asset=>asset.scene).catch(error=>{
        console.warn('Aset '+name+' gagal dimuat. Model bawaan digunakan.',error);
        return null;
      }));
    }
    return loading.get(name);
  }));
  return Object.fromEntries(names.map((name,i)=>[name,models[i]]));
}

export function placePoly(parent,source,{x=0,y=0,z=0,width,height,depth,angle=0}={}){
  const model=source.clone(true);
  const wrapper=new THREE.Group();
  wrapper.add(model);
  model.rotation.y+=angle;
  const bounds=new THREE.Box3().setFromObject(model);
  const size=bounds.getSize(new THREE.Vector3());
  const center=bounds.getCenter(new THREE.Vector3());
  const scale=Math.min(width/size.x,height/size.y,depth/size.z);
  model.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z));
  wrapper.scale.setScalar(scale);
  wrapper.position.set(x,y,z);
  model.traverse(node=>{
    if(node.isMesh){node.castShadow=true;node.receiveShadow=true}
  });
  // Clones share the source geometry and materials, which stay cached between rooms.
  wrapper.userData.polyAsset=true;
  parent.add(wrapper);
  return wrapper;
}
