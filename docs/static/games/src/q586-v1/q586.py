"""q586 Crossing Counter -- shape a ferry rival across marked controller handoffs."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,DOCK,PASSENGER,TACTIC0,TACTIC1,TACTIC2,MARK0,MARK1,GOAL,BAD=2,10,11,14,6,9,12,7,5,13,15
LEVELS=[
 {"name":"First Treatment","seq":(1,2)},{"name":"Repeated Passenger","seq":(1,1)},
 {"name":"Marked Rival","seq":(1,4,3,2)},{"name":"Two Views","seq":(2,1,4,3,2)},
 {"name":"Capacity Counter","seq":(1,2,4,3,2,1,4,3,1)},
 {"name":"Crossing Counter","seq":(2,1,4,3,2,2,4,3,1,2)}]
def advance(s,a):
 controller,recent,rival,load,marks,exploited=s
 if a in (1,2):
  p=(a-1)^controller;recent=(recent+(p,))[-2:];load=(load+a+controller)%6;rival=(sum((i+1)*v for i,v in enumerate(recent))+load+controller)%3
 elif a==3:
  if not marks or marks[-1][0]!=controller:return None
  controller^=1
 elif a==4:marks=marks+((controller,rival,load,tuple(recent)),)
 elif a==5:exploited=(controller,rival,load,marks,tuple(recent))
 return controller,recent,rival,load,marks,exploited
for x in LEVELS:
 s=(0,(),0,0,(),None)
 for a in x["seq"]:s=advance(s,a);assert s is not None
 x["plan"]=x["seq"]+(5,)
def target(x):
 s=(0,(),0,0,(),None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER;f[8:20,8:56]=DOCK
  for i in range(6):f[12:18,9+i*8:14+i*8]=PASSENGER if i==g.load else DOCK
  cols=(TACTIC0,TACTIC1,TACTIC2)
  for i,c in enumerate(cols):f[25:39,8+i*18:22+i*18]=c if i==g.rival else DOCK
  for i,m in enumerate(g.marks[-5:]):f[46:51,8+i*10:15+i*10]=MARK0 if m[0]==0 else MARK1
  f[54:58,8:28]=MARK0 if g.controller==0 else MARK1
  if g.exploited:f[55:59,43:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q586(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q586",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.controller=0;self.recent=();self.rival=self.load=0;self.marks=();self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.controller,self.recent,self.rival,self.load,self.marks,self.exploited),a)
   if s is None:self.bad=True;self.lose()
   else:self.controller,self.recent,self.rival,self.load,self.marks,self.exploited=s
  elif a==6:
   if (self.controller,self.recent,self.rival,self.load,self.marks,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
