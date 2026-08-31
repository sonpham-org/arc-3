"""q538 Breakwater Lesson -- infer a policy whose first choice wakes after two subgoals."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,CHANNEL,SKIFF,TIDE,SUBGOAL,AFFORDANCE,GESTURE,BAD=8,12,11,6,2,4,9,13,15
LEVELS=[
 {"name":"Dormant Choice","plan":(1,2,2,3),"demo":(1,5,2,2,3)},
 {"name":"Changed Tide","plan":(4,1,2,2,3),"demo":(4,1,5,2,2,3)},
 {"name":"Second Intervention","plan":(1,1,2,2,3),"demo":(1,1,5,2,2,3)},
 {"name":"Three Subgoals","plan":(1,2,2,2,3),"demo":(1,5,2,2,2,3)},
 {"name":"Return Current","plan":(1,4,2,2,3,4,3),"demo":(1,5,4,2,2,3,4,3)},
 {"name":"Breakwater Lesson","plan":(1,1,4,2,2,3,4,2,3),"demo":(1,1,5,4,2,2,3,4,2,3)}]
def advance(s,a,x):
 intervention,context,subgoals,skiff,affordance,gesture=s
 if a==1:
  if subgoals:return None
  intervention=(intervention+1)%3
 elif a==2:
  subgoals+=1
  if subgoals>=2:affordance=(intervention+context)%3
 elif a==3:
  if subgoals<2:return None
  skiff=(skiff+affordance+1)%7
 elif a==4:context^=1
 elif a==5:gesture+=1
 return intervention,context,subgoals,skiff,affordance,gesture
def target(x):
 s=(0,0,0,0,0,0)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR
  for i in range(3):f[8+i*10:15+i*10,8:56]=CHANNEL+i
  for i,a in enumerate(g.cfg["demo"]):f[10:14,9+i*5:13+i*5]=(a+5)%16
  f[42:46,8:8+g.intervention*13]=TIDE;f[48:51,8:8+g.subgoals*8]=SUBGOAL;f[53:56,8:12+g.affordance*13]=AFFORDANCE
  f[36:40,8:12+g.skiff*6]=SKIFF
  if g.gesture:f[57:60,42:56]=GESTURE
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q538(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q538",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.intervention=self.context=self.subgoals=self.skiff=self.affordance=self.gesture=0
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.intervention,self.context,self.subgoals,self.skiff,self.affordance,self.gesture),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.intervention,self.context,self.subgoals,self.skiff,self.affordance,self.gesture=s
  elif a==6:
   if (self.intervention,self.context,self.subgoals,self.skiff,self.affordance,self.gesture)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
