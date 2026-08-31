"""q478 Breakwater Dependency -- a dormant key changes every later terminal assembly."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,KEY,SUBGOAL,STOCK,PART,COMPLETE,BAD=1,8,11,6,4,2,9,13,15
def make_plan(need):return (1,2,2)+(3,3,4)*need+(5,)
LEVELS=[{"name":"Dormant Key","need":1},{"name":"Shared Key","need":2},{"name":"Three Branches","need":3},{"name":"Nested Harbor","need":4},{"name":"Stable Channels","need":5},{"name":"Breakwater Dependency","need":6}]
for x in LEVELS:x["plan"]=make_plan(x["need"])
def advance(s,a,x):
 key,subgoals,stock,parts,affordance,complete=s
 if complete is not None:return None
 if a==1:
  if subgoals:return None
  key=(key+1)%3
 elif a==2:
  subgoals+=1
  if subgoals>=2:affordance=key
 elif a==3:stock+=1
 elif a==4:
  if subgoals<2 or stock<2:return None
  stock-=2;parts+=1
 elif a==5:
  if parts!=x["need"] or affordance!=key:return None
  complete=(key,subgoals,stock,parts,affordance)
 return key,subgoals,stock,parts,affordance,complete
def target(x):
 s=(0,0,0,0,None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR
  for i in range(3):f[8+i*10:15+i*10,8:56]=CHANNEL+i
  f[40:44,8:8+g.key*13]=KEY;f[46:49,8:8+g.subgoals*8]=SUBGOAL;f[51:54,8:8+g.stock*5]=STOCK;f[56:59,8:8+g.parts*7]=PART
  if g.complete:f[38:58,56:59]=COMPLETE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q478(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q478",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.key=self.subgoals=self.stock=self.parts=0;self.affordance=self.complete=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.key,self.subgoals,self.stock,self.parts,self.affordance,self.complete),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.key,self.subgoals,self.stock,self.parts,self.affordance,self.complete=s
  elif a==6:
   if (self.key,self.subgoals,self.stock,self.parts,self.affordance,self.complete)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
