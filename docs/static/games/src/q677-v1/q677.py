"""q677 Spectrum Analogy -- transfer an affine direction and magnitude across unlike surfaces."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GALLERY,PRISM,AGENT,DIRECTION,MAGNITUDE,SURFACE,TRANSFER,BAD=10,9,14,12,6,11,13,8,15
LEVELS=[
 {"name":"First Ray","ops":(1,),"surface":0},{"name":"Reflected Ray","ops":(1,2),"surface":0},
 {"name":"Surface Shift","ops":(1,1,2),"surface":1},{"name":"Affine Analogy","ops":(2,1,1,2),"surface":2},
 {"name":"Agent Transfer","ops":(1,2,1,1,2),"surface":2},{"name":"Spectrum Analogy","ops":(2,1,2,1,1,2),"surface":3}]
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def advance(s,a,x):
 magnitude,direction,memory,surface,transferred=s
 if a==1:magnitude=(magnitude+1)%5
 elif a==2:direction*=-1
 elif a==3:memory=(magnitude,direction)
 elif a==4:surface=(surface+1)%4
 elif a==5:
  if memory is None:return None
  transferred=(memory[0]+surface,memory[1]*(-1 if surface%2 else 1))
 return magnitude,direction,memory,surface,transferred
def target(x):
 s=(0,1,None,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GALLERY;f[8:34,8:29]=PRISM;f[8:34,35:56]=AGENT
  for i in range(5):f[11+i*4:14+i*4,11:26]=MAGNITUDE if i<=g.magnitude else PRISM
  f[39:43,8:28]=DIRECTION if g.direction>0 else SURFACE;f[47:51,8:8+g.surface*12]=SURFACE
  if g.transferred:f[54:59,39:56]=TRANSFER
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q677(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q677",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.magnitude=0;self.direction=1;self.memory=None;self.surface=0;self.transferred=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.magnitude,self.direction,self.memory,self.surface,self.transferred),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.magnitude,self.direction,self.memory,self.surface,self.transferred=s
  elif a==6:
   if (self.magnitude,self.direction,self.memory,self.surface,self.transferred)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
