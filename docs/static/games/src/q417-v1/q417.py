"""q417 Canopy Revision -- recalibrate a worn orchard rule through a narrow store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,SHADE,SEED,STORE,WEAR,FAIL,REPAIR,BAD=7,10,9,14,12,5,11,6,15
LEVELS=[{"name":"Single Bin","rule":1,"capacity":1,"plan":(1,4,5)},{"name":"Paired Bin","rule":2,"capacity":2,"plan":(2,1,4,5)},{"name":"Reused Store","rule":3,"capacity":2,"plan":(3,2,4,1,4,5)},{"name":"Full Terrace","rule":1,"capacity":3,"plan":(1,3,2,4,5)},{"name":"Second Wear","rule":2,"capacity":2,"plan":(2,1,4,3,1,4,5)},{"name":"Canopy Revision","rule":3,"capacity":3,"plan":(3,1,2,4,3,2,1,4,5)}]
def advance(s,a,x):
 buffer,output,wear,failed,repair=s;buffer=list(buffer);output=list(output)
 if a in (1,2,3):
  if len(buffer)>=x["capacity"]:return None
  buffer.append((a,(a+x["rule"]+wear)%5))
 elif a==4:
  if not buffer:return None
  failed=(tuple(buffer),wear,(x["rule"]+wear)%4);output.extend(buffer);buffer=[];wear=(wear+1)%4
 elif a==5:
  if failed is None:return None
  repair=(failed[2],sum(v for _,v in output)%5,len(output))
 return tuple(buffer),tuple(output),wear,failed,repair
def target(x):
 s=((),(),0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD;f[8:31,7:29]=SHADE;f[8:31,35:57]=STORE
  for i,(_,v) in enumerate(g.buffer):f[12+i*7:17+i*7,11:18]=SEED-v
  for i,(_,v) in enumerate(g.output[-6:]):f[12+(i%3)*7:17+(i%3)*7,39+(i//3)*8:46+(i//3)*8]=SEED-v
  f[37:40,8:11+g.wear*11]=WEAR;f[47:50,8:24]=FAIL if g.failed else SHADE;f[54:57,40:56]=REPAIR if g.repair else STORE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q417(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q417",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.buffer=();self.output=();self.wear=0;self.failed=self.repair=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.buffer,self.output,self.wear,self.failed,self.repair),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.buffer,self.output,self.wear,self.failed,self.repair=s
  elif a==6:
   if (self.buffer,self.output,self.wear,self.failed,self.repair)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
