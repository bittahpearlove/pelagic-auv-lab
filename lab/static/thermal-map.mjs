// Prescribed, static teaching fields. No heat-equation/PDE solver is used.
export function temperatureAt(x,z,p){
  const shape=p.shape||'layer',slope=(shape==='tilted'||shape==='combined')?.16:0;
  if(shape==='front')return 22-p.drop/2*(1+Math.tanh((x-4)/(5*p.width)));
  const centre=p.center+slope*(x-4);
  let value=22-p.drop/2*(1+Math.tanh((z-centre)/p.width));
  if(shape==='patch'||shape==='combined')value+=2*Math.exp(-.5*(((x-5.3)/.75)**2+((z-p.center-.35)/.3)**2));
  return value;
}
export function trueGradient(x,z,p){
  const h=.001;
  return {gx:(temperatureAt(x+h,z,p)-temperatureAt(x-h,z,p))/(2*h),gz:(temperatureAt(x,z+h,p)-temperatureAt(x,z-h,p))/(2*h)};
}
const clamp=v=>Math.max(0,Math.min(1,v));
export class ThermalMap {
  constructor(){this.clear();}
  clear(){this.cells=new Map();this.version=0;this.samples=0;}
  // Aggregate spatial bins: waiting in one place does not create extra spatial coverage.
  add(x,z,temperature){
    if(![x,z,temperature].every(Number.isFinite)||x<0||x>8||z<0||z>3)return;
    const key=`${Math.min(39,Math.floor(x/.2))}:${Math.min(29,Math.floor(z/.1))}`;
    const old=this.cells.get(key)||{x:0,z:0,t:0,n:0};old.n++;
    for(const [name,value] of [['x',x],['z',z],['t',temperature]])old[name]+=(value-old[name])/old.n;
    this.cells.set(key,old);this.samples++;this.version++;
  }
  estimate(x,z){
    const neighbours=[];
    for(const cell of this.cells.values()){
      const dx=(cell.x-x),dz=(cell.z-z)/.5,d2=dx*dx+dz*dz;
      if(d2<2.25)neighbours.push({dx,dz,t:cell.t,d2,w:Math.exp(-2*d2)});
    }
    neighbours.sort((a,b)=>a.d2-b.d2);const a=neighbours.slice(0,48);
    if(!a.length||a[0].d2>.42)return null;
    let W=0,mx=0,mz=0,mt=0;
    for(const q of a){W+=q.w;mx+=q.w*q.dx;mz+=q.w*q.dz;mt+=q.w*q.t;}mx/=W;mz/=W;mt/=W;
    let xx=0,zz=0,xz=0,xt=0,zt=0;
    for(const q of a){const dx=q.dx-mx,dz=q.dz-mz,dt=q.t-mt;xx+=q.w*dx*dx;zz+=q.w*dz*dz;xz+=q.w*dx*dz;xt+=q.w*dx*dt;zt+=q.w*dz*dt;}
    const det=xx*zz-xz*xz,trace=xx+zz,geometry=trace>0?det/(trace*trace):0;
    const resolved=a.length>=5&&geometry>.015&&xx/W>.001&&zz/W>.001;
    if(!resolved)return {temperature:mt,gradient:null,coverage:.12,reason:'Need samples in different directions',bins:a.length};
    const gx=(xt*zz-zt*xz)/det,gz=(zt*xx-xt*xz)/det;
    let residual=0;for(const q of a)residual+=q.w*(q.t-(mt+gx*(q.dx-mx)+gz*(q.dz-mz)))**2;
    residual=Math.sqrt(residual/W);
    // A support/fit heuristic, not a calibrated statistical confidence interval.
    const angles=a.map(q=>Math.atan2(q.dz,q.dx)).sort((a,b)=>a-b);
    let gap=angles[0]+2*Math.PI-angles.at(-1);for(let i=1;i<angles.length;i++)gap=Math.max(gap,angles[i]-angles[i-1]);
    const surrounded=gap<=Math.PI+.05;
    const coverage=clamp((1-Math.sqrt(a[0].d2)/.8)*Math.min(1,geometry/.12)*(1/(1+residual/.2))*(surrounded?1:.35));
    return {temperature:mt-gx*mx-gz*mz,gradient:surrounded?{gx,gz:gz/.5}:null,coverage,residual,bins:a.length,reason:surrounded?'Local plane fit':'At edge of sampled area'};
  }
}
