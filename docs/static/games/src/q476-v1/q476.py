"""q476 Palimpsest Dependency -- reuse one failed prerequisite trace across branches."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARCHIVE,SHELF,TILE,TRACE,PART,REPAIR,COMPLETE,BAD=7,8,11,6,15,2,4,13,10
def make_plan(need):return (3,4,4,3)+(4,4,3)*(need-1)+(5,)
LEVELS=[{"name":"Missing Pair","need":1},{"name":"Shared Trace","need":2},{"name":"Three Branches","need":3},{"name":"Nested Archive","need":4},{"name":"Stable Subgoals","need":5},{"name":"Palimpsest Dependency","need":6}]
for x in LEVELS:x["plan"]=make_plan(x["need"])
def advance(s,a,x):
 stock,parts,failure,repaired,complete=s;stock=list(stock)
 if complete is not None:return None
 if a==1:stock[0]+=1
 elif a==2:stock[1]+=1
 elif a==3:
  if stock[0]<1 or stock[1]<1:
   failure=(max(0,1-stock[0]),max(0,1-stock[1]));return tuple(stock),parts,failure,repaired,complete
  stock[0]-=1;stock[1]-=1;parts+=1
 elif a==4:
  if failure is None:return None
  i=0 if stock[0]<1 else 1;stock[i]+=1;repaired+=1
 elif a==5:
  if parts!=x["need"]:return None
  complete=(tuple(stock),parts,failure,repaired)
 return tuple(stock),parts,failure,repaired,complete
def target(x):
 s=((0,0),0,None,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARCHIVE;f[9:34,8:29]=SHELF;f[9:34,35:56]=SHELF
  f[29-g.stock[0]*5:31,11:26]=TILE;f[29-g.stock[1]*5:31,38:53]=TILE+2
  f[36:39,8:56]=REPAIR
  f[40:44,8:8+g.parts*7]=PART;f[47:50,8:8+g.repaired*5]=REPAIR
  if g.failure:f[53:57,8:34]=TRACE
  if g.complete:f[38:58,56:59]=COMPLETE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q476(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q476",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(0,0);self.parts=0;self.failure=None;self.repaired=0;self.complete=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.parts,self.failure,self.repaired,self.complete),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.parts,self.failure,self.repaired,self.complete=s
  elif a==6:
   if (self.stock,self.parts,self.failure,self.repaired,self.complete)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
