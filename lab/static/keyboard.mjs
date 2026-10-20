// Track physical keys separately, so releasing W does not release a held ArrowUp.
const bindings={KeyW:'up',ArrowUp:'up',KeyA:'left',ArrowLeft:'left',KeyS:'down',ArrowDown:'down',KeyD:'right',ArrowRight:'right'};
export class KeyboardDrive {
  constructor(){this.keys=new Set();}
  press(code,repeat=false){if(!bindings[code])return false;if(!repeat)this.keys.add(code);return true;}
  release(code){this.keys.delete(code);}
  clear(){this.keys.clear();}
  directions(){return new Set([...this.keys].map(code=>bindings[code]));}
}
