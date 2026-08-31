"""q324 Honeycomb Survey -- allocate evidence while tracking local and enclosing clocks."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,APIARY,CELL,COURIER,LOCAL,GLOBAL,EVIDENCE,POLICY,BAD=9,12,14,5,6,11,4,7,15
LEVELS=[{"name":"One Scent","cycle":2,"budget":1,"plan":(1,5)},{"name":"Outer Cell","cycle":2,"budget":2,"plan":(2,4,1,5)},{"name":"Evidence Union","cycle":3,"budget":3,"plan":(1,3,4,2,5)},{"name":"Two Clocks","cycle":3,"budget":3,"plan":(2,4,3,1,5)},{"name":"Nested Return","cycle":4,"budget":4,"plan":(3,1,4,2,3,5)},{"name":"Honeycomb Survey","cycle":4,"budget":4,"plan":(1,4,3,2,4,1,5)}]
def advance(s,a,x):
 local,global_,evidence,cost,policy=s;evidence=list(evidence)
 if a in (1,2,3):evidence.append((a,local,global_,(a+local+global_)%4));cost+=1
 elif a==5:policy=(sum(v for *_,v in evidence)+local+global_)%4
 local+=1
 if local>=x["cycle"]:local=0;global_=(global_+1)%4
 return local,global_,tuple(evidence),cost,policy
def target(x):
 s=(0,0,(),0,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=APIARY
  for i in range(3):x=8+i*18;f[9:33,x:x+14]=CELL;f[15+i*4:22+i*4,x+4:x+10]=COURIER+i
  for i,(*_,v) in enumerate(g.evidence[-6:]):f[37+i*3:39+i*3,8:11+v*11]=EVIDENCE
  f[53:56,8:11+g.local*11]=LOCAL;f[57:60,8:11+g.global_*11]=GLOBAL;f[57:60,48:56]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q324(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q324",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.global_=self.cost=self.policy=0;self.evidence=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   self.local,self.global_,self.evidence,self.cost,self.policy=advance((self.local,self.global_,self.evidence,self.cost,self.policy),a,x)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.local,self.global_,self.evidence,self.cost,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
