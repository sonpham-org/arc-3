"""q667 Catalyst Analogy -- store a source relation before transforming and executing its target."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,SOURCE,TARGET,RELATION,MEMORY,SURFACE,TRANSFER,BAD=5,12,9,14,10,6,13,11,15
LEVELS=[
 {"name":"First Relation","ops":(1,),"surface":0},{"name":"Reflected Relation","ops":(1,2),"surface":0},
 {"name":"Surface Shift","ops":(1,1,2),"surface":1},{"name":"Stored Analogy","ops":(2,1,1,2),"surface":2},
 {"name":"Distant Transfer","ops":(1,2,1,1,2),"surface":2},{"name":"Catalyst Analogy","ops":(2,1,2,1,1,2),"surface":3}]
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def advance(s,a,x):
 relation,source,memory,target_orientation,visible,transferred=s
 if a==1:relation=(relation+1)%4;source=(source+1)%4
 elif a==2:relation=(-relation)%4;source=(source+2)%4
 elif a==3:memory=(relation+source)%4;visible=1
 elif a==4:target_orientation=(target_orientation+2)%4;source=(source+1)%4
 elif a==5:
  if memory is None:return None
  visible=0;transferred=(memory+target_orientation)%4
 return relation,source,memory,target_orientation,visible,transferred
def target(x):
 s=(0,0,None,0,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY;f[8:34,8:29]=SOURCE;f[8:34,35:56]=TARGET
  for i in range(4):f[11+i*5:14+i*5,11:26]=RELATION if i==g.relation else SOURCE
  f[11+g.target_orientation*5:14+g.target_orientation*5,38:53]=SURFACE;f[40:44,8:28]=MEMORY
  if g.memory is not None:f[40:45,36:36+g.memory*5+5]=MEMORY
  if g.transferred is not None:f[54:59,39:56]=TRANSFER+g.transferred
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q667(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q667",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.relation=self.source=self.target_orientation=0;self.memory=self.transferred=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.relation,self.source,self.memory,self.target_orientation,self.visible,self.transferred),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.relation,self.source,self.memory,self.target_orientation,self.visible,self.transferred=s
  elif a==6:
   if (self.relation,self.source,self.memory,self.target_orientation,self.visible,self.transferred)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
