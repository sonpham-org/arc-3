"""q477 Canopy Dependency -- reuse one shared glider through a capacity-limited seed store."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ORCHARD,TERRACE,SEED,STORE,SHARED,BRANCH,SHADE,DONE,BAD=10,14,11,12,9,6,13,8,7,15
LEVELS=[
 {"name":"First Branch","need":1,"capacity":2},{"name":"Shared Glider","need":2,"capacity":2},
 {"name":"Three Branches","need":3,"capacity":2},{"name":"Nested Canopy","need":4,"capacity":3},
 {"name":"Seasonal Order","need":5,"capacity":3},{"name":"Canopy Dependency","need":6,"capacity":2}]
def make_plan(x):
 p=[1,1,2];season=branches=0
 while branches<x["need"]:
  if season!=branches%2:p.append(4);season^=1
  p.extend((1,3));branches+=1
 p.append(5);return tuple(p)
for x in LEVELS:x["plan"]=make_plan(x)
def advance(s,a,x):
 store,shared,branches,season,complete=s
 if a==1:
  if store>=x["capacity"]:return None
  store+=1
 elif a==2:
  if shared or store<2:return None
  store-=2;shared=1
 elif a==3:
  if not shared or not store or season!=branches%2:return None
  store-=1;branches+=1
 elif a==4:season^=1
 elif a==5:
  if not shared or branches!=x["need"]:return None
  complete=(shared,branches,season)
 return store,shared,branches,season,complete
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ORCHARD
  for i in range(4):f[8+i*8:14+i*8,8:56]=TERRACE+i%2
  f[41:45,8:8+g.store*12]=STORE;f[48:52,8:8+g.branches*7]=BRANCH;f[55:59,8:28]=SHADE+g.season
  if g.shared:f[41:46,39:56]=SHARED
  if g.complete:f[54:59,39:56]=DONE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q477(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q477",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.store=self.shared=self.branches=self.season=0;self.complete=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.store,self.shared,self.branches,self.season,self.complete),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.store,self.shared,self.branches,self.season,self.complete=s
  elif a==6:
   if (self.store,self.shared,self.branches,self.season,self.complete)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
