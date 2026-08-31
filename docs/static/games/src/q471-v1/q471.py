"""q471 Aurora Dependency -- reuse lower patterns through a visible hysteresis loop."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,SHARED,BRANCH,HYSTERESIS,GOAL,BAD=9,10,12,14,5,11,6,7,15
LEVELS=[{"name":"One Curtain","branches":1,"plan":(1,4,5)},{"name":"Shared Crystal","branches":1,"plan":(2,1,4,5)},{"name":"Two Dependencies","branches":2,"plan":(1,2,4,3,4,5)},{"name":"Reused Pattern","branches":2,"plan":(3,1,2,4,2,1,4,5)},{"name":"Hysteresis Fork","branches":3,"plan":(1,3,4,2,4,1,2,3,4,5)},{"name":"Aurora Dependency","branches":3,"plan":(3,1,2,4,1,3,4,2,1,4,5)}]
def advance(s,a,x):
 motes,shared,branches,control,hysteresis,terminal=s;motes=list(motes);branches=list(branches)
 if a in (1,2,3):control=a-1;motes[control]+=1;hysteresis=(hysteresis+control+1)%7
 elif a==4:
  if not sum(motes):return None
  shared=(sum((i+1)*v for i,v in enumerate(motes))+hysteresis+len(branches))%8;branches.append((shared,control,hysteresis));motes=[0,0,0];control=(control+1)%3;hysteresis=(hysteresis+shared+1)%7
 elif a==5:
  if len(branches)<x["branches"]:return None
  terminal=(shared,tuple(branches),control,hysteresis)
 return tuple(motes),shared,tuple(branches),control,hysteresis,terminal
def target(x):
 s=((0,0,0),0,(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,v in enumerate(g.motes):x=10+i*17;f[25-v*4:28,x:x+10]=MOTE-i
  for i,(v,_,_) in enumerate(g.branches[-6:]):f[36+i*3:38+i*3,8:11+v*6]=BRANCH
  f[48:51,8:11+g.hysteresis*7]=HYSTERESIS;f[53:56,8:24]=SHARED;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q471(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q471",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.motes=(0,0,0);self.shared=0;self.branches=();self.control=self.hysteresis=0;self.terminal=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.motes,self.shared,self.branches,self.control,self.hysteresis,self.terminal),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.motes,self.shared,self.branches,self.control,self.hysteresis,self.terminal=s
  elif a==6:
   if (self.motes,self.shared,self.branches,self.control,self.hysteresis,self.terminal)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
