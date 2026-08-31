"""a166 Iterative Deepening -- increase complete search bounds without overspending."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CONSOLE,DEPTH,SEARCHED,GOAL,FOUND,COST,PULSE,PLAN,EXCESS=2,8,7,10,14,4,6,13,11,9
BAD=15
LEVELS=[
 {"name":"Raise Depth","seq":(1,)},{"name":"Lower Depth","seq":(2,)},
 {"name":"Pulse Search","seq":(3,1)},{"name":"Find Short Plan","seq":(1,2,3,4,2)},
 {"name":"Control Cost","seq":(1,3,2,1,4,3,2)},{"name":"Iterative Deepening","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 depth,goal_depth,pulses,cost,found,plan_len,history,snapshot=s
 if a==1:depth=min(8,depth+1);history=(history+(1,))[-8:]
 elif a==2:depth=max(0,depth-1);history=(history+(2,))[-8:]
 elif a==3:pulses=(pulses+1)%8;cost=(cost+(2**depth))%64;found=int(depth>=goal_depth);plan_len=goal_depth if found else 0;history=(history+(3,))[-8:]
 elif a==4:history=(history+(4,))[-8:]
 elif a==5:snapshot=(depth,goal_depth,pulses,cost,found,plan_len,history)
 return depth,goal_depth,pulses,cost,found,plan_len,history,snapshot
for q in LEVELS:
 s=(0,4,0,0,0,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CONSOLE
  for i in range(8):f[46-i*5:50-i*5,10:26]=SEARCHED if i<g.depth else DEPTH
  f[46-g.goal_depth*5:50-g.goal_depth*5,29:45]=GOAL;f[10:18,48:56]=FOUND if g.found else EXCESS;f[54:58,8:8+min(12,g.cost)*4]=COST;f[7:10,8:8+g.pulses*6]=PULSE;f[54:58,51:51+g.plan_len]=PLAN
  if g.bad:f[1:4,18:46]=BAD
  return f
class A166(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a166",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.depth,self.goal_depth,self.pulses,self.cost,self.found,self.plan_len,self.history,self.snapshot=(0,4,0,0,0,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.depth,self.goal_depth,self.pulses,self.cost,self.found,self.plan_len,self.history,self.snapshot=advance((self.depth,self.goal_depth,self.pulses,self.cost,self.found,self.plan_len,self.history,self.snapshot),a)
  elif a==6:
   if (self.depth,self.goal_depth,self.pulses,self.cost,self.found,self.plan_len,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
