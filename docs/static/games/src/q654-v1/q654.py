"""q654 Honeycomb Analogy -- transfer a relation only at nested-clock boundaries."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HIVE,CELL,SOURCE,TARGET,LOCAL,OUTER,PROOF,BAD=6,8,12,6,2,4,9,13,15
LEVELS=[
 {"name":"One Cycle","cycle":2,"plan":(1,2,2,3,5)},{"name":"Three-Step Cycle","cycle":3,"plan":(1,2,2,2,3,5)},
 {"name":"Whole Chunk","cycle":3,"plan":(1,4,3,5)},{"name":"Two Outer Cycles","cycle":4,"plan":(1,4,4,3,5)},
 {"name":"Changed Relation","cycle":4,"plan":(1,1,2,2,2,2,3,5)},{"name":"Honeycomb Analogy","cycle":5,"plan":(1,4,1,4,3,1,3,5)}]
def advance(s,a,x):
 source,target_relation,local,outer,proof=s
 if a==1:source=(source+1)%4
 elif a==2:
  local+=1
  if local==x["cycle"]:local=0;outer=(outer+1)%4
 elif a==3:
  if local:return None
  target_relation=(source+outer)%4
 elif a==4:outer=(outer+1)%4
 elif a==5:
  if target_relation!=(source+outer)%4:return None
  proof=(source,target_relation,local,outer)
 return source,target_relation,local,outer,proof
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HIVE
  for i in range(4):
   f[9+i*9:15+i*9,8:25]=SOURCE if i==g.source else CELL
   f[9+i*9:15+i*9,39:56]=TARGET if i==g.target_relation else CELL+1
  f[48:51,8:8+g.local*8]=LOCAL;f[53:56,8:8+g.outer*10]=OUTER
  if g.proof:f[44:58,57:60]=PROOF
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q654(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q654",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.source=self.target_relation=self.local=self.outer=0;self.proof=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.source,self.target_relation,self.local,self.outer,self.proof),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.source,self.target_relation,self.local,self.outer,self.proof=s
  elif a==6:
   if (self.source,self.target_relation,self.local,self.outer,self.proof)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
