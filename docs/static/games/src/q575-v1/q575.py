"""q575 Waystation Counter -- shape a caravan rival through the last two policies."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SAND,DUNE,WALKER,TACTIC0,TACTIC1,TACTIC2,HISTORY,GOAL,BAD=2,7,11,14,10,9,12,6,13,15
LEVELS=[
 {"name":"First Treatment","seq":(1,)},{"name":"Two Policies","seq":(1,2)},
 {"name":"Shifted Rival","seq":(1,3,2)},{"name":"Persistent Counter","seq":(2,1,4,2)},
 {"name":"Punish Repetition","seq":(1,1,3,2,4,1)},{"name":"Waystation Counter","seq":(2,1,2,3,1,4,2,2,3)}]
def advance(s,a,x):
 recent,shift,pos,rival,exploited=s
 if a in (1,2):
  p=a-1;recent=(recent+(p,))[-2:];pos=(pos+a+shift)%9;rival=(sum((i+1)*v for i,v in enumerate(recent))+shift+int(len(recent)==2 and recent[0]==recent[1]))%3
 elif a==3:shift=(shift+1)%3;rival=(rival+1)%3
 elif a==4:pos=0
 elif a==5:
  if rival!=x["goal"]:return None
  exploited=(rival,pos,shift,recent)
 return recent,shift,pos,rival,exploited
for x in LEVELS:
 s=((),0,0,0,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=s[3];x["plan"]=x["seq"]+(5,)
def target(x):
 s=((),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SAND;f[8:21,8:56]=DUNE
  for i in range(9):x=9+i*5;f[14:19,x:x+3]=WALKER if i==g.pos else DUNE
  cols=(TACTIC0,TACTIC1,TACTIC2)
  for i,c in enumerate(cols):f[27:41,8+i*18:22+i*18]=c if i==g.rival else HISTORY
  for i,v in enumerate(g.recent):f[47:52,8+i*13:18+i*13]=cols[v]
  f[54:58,37:37+g.shift*6+5]=DUNE
  if g.exploited:f[55:59,8:27]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q575(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q575",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.shift=self.pos=self.rival=0;self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.recent,self.shift,self.pos,self.rival,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.recent,self.shift,self.pos,self.rival,self.exploited=s
  elif a==6:
   if (self.recent,self.shift,self.pos,self.rival,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
