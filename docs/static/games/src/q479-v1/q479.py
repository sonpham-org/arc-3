"""q479 Strata Dependency -- restore a physical probe while retaining knowledge for shared branches."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,ORE,WORLD,KNOWLEDGE,SHARED,BRANCH,DONE,BAD=10,8,11,12,9,6,14,13,7,15
LEVELS=[
 {"name":"First Support","probes":1,"need":1},{"name":"Shared Support","probes":2,"need":2},
 {"name":"Three Branches","probes":3,"need":3},{"name":"Restored Quarry","probes":4,"need":4},
 {"name":"Persistent Knowledge","probes":4,"need":5},{"name":"Strata Dependency","probes":4,"need":6}]
for x in LEVELS:x["plan"]=(1,)*x["probes"]+(2,3)+(4,)*x["need"]+(5,)
def advance(s,a,x):
 world,knowledge,shared,branches,restored,complete=s
 if a==1:world=(world+1)%4;knowledge|=1<<world
 elif a==2:world=0;restored+=1
 elif a==3:
  if world or knowledge.bit_count()<min(x["probes"],4):return None
  shared=1
 elif a==4:
  bit=1<<((branches%x["probes"]+1)%4)
  if not shared or not knowledge&bit:return None
  branches+=1
 elif a==5:
  if not shared or branches!=x["need"]:return None
  complete=(knowledge,branches,restored)
 return world,knowledge,shared,branches,restored,complete
def target(x):
 s=(0,0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(4):f[8+i*8:14+i*8,8:56]=FAULT+i%2
  f[11+g.world*8:15+g.world*8,11:20]=WORLD
  for i in range(4):
   if g.knowledge&(1<<i):f[41:45,8+i*12:17+i*12]=KNOWLEDGE
  f[49:53,8:8+g.branches*7]=BRANCH
  if g.shared:f[55:59,8:28]=SHARED
  if g.complete:f[54:59,39:56]=DONE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q479(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q479",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.world=self.knowledge=self.shared=self.branches=self.restored=0;self.complete=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.world,self.knowledge,self.shared,self.branches,self.restored,self.complete),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.world,self.knowledge,self.shared,self.branches,self.restored,self.complete=s
  elif a==6:
   if (self.world,self.knowledge,self.shared,self.branches,self.restored,self.complete)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
