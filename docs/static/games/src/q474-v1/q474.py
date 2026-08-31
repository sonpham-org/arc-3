"""q474 Honeycomb Dependency -- build shared prerequisites at nested-clock boundaries."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,NECTAR,LOCAL,OUTER,PART,COMPLETE,BAD=11,8,12,6,2,9,4,13,15
def make_plan(need,cycle):return ((1,1)+(2,)*(cycle-2)+(3,))*need+(5,)
LEVELS=[{"name":"First Cell","need":1,"cycle":2},{"name":"Shared Nectar","need":2,"cycle":3},{"name":"Three Branches","need":3,"cycle":4},{"name":"Nested Apiary","need":4,"cycle":3},{"name":"Stable Cells","need":5,"cycle":4},{"name":"Honeycomb Dependency","need":6,"cycle":5}]
for x in LEVELS:x["plan"]=make_plan(x["need"],x["cycle"])
def tick(local,outer,cycle):
 local+=1
 if local==cycle:local=0;outer+=1
 return local,outer
def advance(s,a,x):
 nectar,parts,local,outer,complete=s
 if complete is not None:return None
 if a==1:nectar+=1;local,outer=tick(local,outer,x["cycle"])
 elif a==2:local,outer=tick(local,outer,x["cycle"])
 elif a==3:
  if local or nectar<2:return None
  nectar-=2;parts+=1
 elif a==4:outer+=1
 elif a==5:
  if parts!=x["need"]:return None
  complete=(nectar,parts,local,outer)
 return nectar,parts,local,outer,complete
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE
  for y in (8,20,32):
   for x in (8,20,32,44):f[y:y+8,x:x+9]=CELL+(x//12+y//12)%2
  f[40:42,8:56]=NECTAR;f[42:46,8:8+g.nectar*5]=NECTAR;f[48:51,8:8+g.local*8]=LOCAL;f[53:56,8:8+g.outer*5]=OUTER;f[57:60,8:8+g.parts*7]=PART
  if g.complete:f[38:58,56:59]=COMPLETE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q474(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q474",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.nectar=self.parts=self.local=self.outer=0;self.complete=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.nectar,self.parts,self.local,self.outer,self.complete),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.nectar,self.parts,self.local,self.outer,self.complete=s
  elif a==6:
   if (self.nectar,self.parts,self.local,self.outer,self.complete)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
