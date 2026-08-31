"""q577 Catalyst Counter -- shape, observe, then hide-execute a stored rival counter."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,TACTIC0,TACTIC1,TACTIC2,MEMORY,HIDDEN,EXPLOIT,BAD=2,12,9,14,10,6,13,11,15
LEVELS=[
 {"name":"Paired Tactic","seq":(1,1,3,4)},{"name":"Split Tactic","seq":(1,2,3,4)},
 {"name":"Three Treatments","seq":(2,1,2,3,4)},{"name":"Stored Counter","seq":(1,2,1,2,3,4)},
 {"name":"Decoy Counter","seq":(2,2,1,5,2,3,4)},{"name":"Catalyst Counter","seq":(1,2,2,1,5,2,3,4)}]
def advance(s,a,x):
 hist,rival,orientation,memory,visible,exploited=s;hist=list(hist)
 if a in (1,2):
  hist=(hist+[a-1])[-3:];orientation=(orientation+a)%4;rival=(sum((i+1)*v for i,v in enumerate(hist))+orientation)%3
 elif a==3:memory=rival;visible=1
 elif a==4:
  if memory is None or memory!=rival:return None
  visible=0;exploited=(memory,orientation)
 elif a==5:rival=(rival+1)%3;orientation=(orientation+2)%4
 return tuple(hist),rival,orientation,memory,visible,exploited
for x in LEVELS:x["plan"]=x["seq"]
def target(x):
 s=((),0,0,None,1,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=REFINERY
  for i,c in enumerate((TACTIC0,TACTIC1,TACTIC2)):f[8:29,8+i*17:22+i*17]=c
  f[33:38,8+g.rival*17:22+g.rival*17]=EXPLOIT;f[43:47,8:28]=MEMORY;f[43:47,36:56]=TACTIC0+g.orientation
  if g.memory is not None:f[50:54,8:8+g.memory*14]=MEMORY
  if not g.visible:f[55:59,8:28]=HIDDEN
  if g.exploited:f[54:59,39:56]=EXPLOIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q577(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q577",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.hist=();self.rival=self.orientation=0;self.memory=self.exploited=None;self.visible=1
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.hist,self.rival,self.orientation,self.memory,self.visible,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.hist,self.rival,self.orientation,self.memory,self.visible,self.exploited=s
  elif a==6:
   if (self.hist,self.rival,self.orientation,self.memory,self.visible,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
