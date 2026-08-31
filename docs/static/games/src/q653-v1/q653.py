"""q653 Ember Analogy -- transfer a heat-band relation to changing clay vessels."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,KILN,BAND,VESSEL,SURFACE,TRANSFER,PROOF,RESOURCE,BAD=14,9,2,6,11,4,7,10,15
LEVELS=[
 {"name":"Turn and Transfer","plan":(1,3,5),"budget":5},{"name":"Changed Surface","plan":(4,1,3,5),"budget":6},
 {"name":"Double Turn","plan":(1,1,4,3,5),"budget":7},{"name":"Reflected Band","plan":(2,4,4,3,5),"budget":7},
 {"name":"Surface Invariance","plan":(1,4,2,4,3,5),"budget":8},{"name":"Ember Analogy","plan":(4,1,2,1,4,3,5),"budget":9}]
def advance(s,a,x):
 band,vessel,surface,proof,resource=s
 if resource<=0:return None
 resource-=1
 if a==1:band=(band+1)%4
 elif a==2:band=(-band)%4
 elif a==3:vessel=(band+surface)%4
 elif a==4:surface=(surface+1)%4
 elif a==5:
  if vessel!=(band+surface)%4:return None
  proof+=1
 return band,vessel,surface,proof,resource
def target(x):
 s=(0,0,0,0,x["budget"])
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=KILN
  for i in range(4):f[9+i*9:15+i*9,8:25]=BAND if i==g.band else SURFACE
  for i in range(4):f[9+i*9:15+i*9,39:56]=VESSEL if i==g.vessel else SURFACE
  f[47:51,8:12+g.surface*10]=TRANSFER;f[53:57,8:8+g.resource*5]=RESOURCE
  if g.proof:f[44:58,57:60]=PROOF
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q653(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q653",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.band=self.vessel=self.surface=self.proof=0;self.resource=self.cfg["budget"]
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.band,self.vessel,self.surface,self.proof,self.resource),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.band,self.vessel,self.surface,self.proof,self.resource=s
  elif a==6:
   if (self.band,self.vessel,self.surface,self.proof,self.resource)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
