"""q351 Aurora Rig -- build dual-effect crystal tools under hysteretic curtains."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,PART,RIG,CONTROL,ROUTE,GOAL,BAD=15,10,6,14,12,9,11,0,8
LEVELS=[{"name":"First Redirect","plan":(1,4)},{"name":"Joined Light","plan":(2,1,4)},{"name":"Support Sweep","plan":(3,2,4,5)},{"name":"Dual Effect","plan":(1,3,2,4,5)},{"name":"Hysteresis Rig","plan":(2,1,5,3,4,5)},{"name":"Aurora Rig","plan":(3,1,2,5,3,4,1,5)}]
def advance(s,a):
 parts,rig,control,direction,route=s;parts=list(parts)
 if a in (1,2,3):parts[a-1]+=1;route=(route+a+parts[a-1])%5
 elif a==4:
  if not sum(parts):return None
  rig+=1;route=(route+parts[0]*2+parts[1]*3+parts[2]+control)%5;parts=[max(0,v-1) for v in parts]
 elif a==5:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
  route=(route+control+direction)%5
 return tuple(parts),rig,control,direction,route
def target(x):
 s=((0,0,0),0,0,1,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[8:15,8:56]=CURTAIN
  for i,n in enumerate(g.parts):x=9+i*17;f[19:22,x:x+11]=PART-i;f[24:24+n*6,x:x+11]=PART-i
  for i in range(g.rig):f[43+i*4:46+i*4,10:54]=RIG
  f[52:55,8:8+g.control*14]=CONTROL;f[57:60,8:8+g.route*11]=ROUTE
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q351(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q351",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=(0,0,0);self.rig=self.control=self.route=0;self.direction=1
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.rig,self.control,self.direction,self.route),a)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.rig,self.control,self.direction,self.route=s
  elif a==6:
   if (self.parts,self.rig,self.control,self.direction,self.route)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
