"""q732 Semaphore Gradient -- conserve signal mass through capacity-limited relay beams."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,TOWER,FLAG,BEAM,MASS,CAPACITY,GOAL,BAD=3,11,5,14,9,6,12,13,15
LEVELS=[{"name":"First Transfer","seq":(1,)},{"name":"Beam Capacity","seq":(2,1)},{"name":"Phase Shift","seq":(3,1,2)},{"name":"Miniature Test","seq":(4,2,1,3)},{"name":"Threshold Route","seq":(2,3,1,4,2,1)},{"name":"Semaphore Gradient","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 mass,phase,capacity,tests,commit=s;v=list(mass)
 if a==1:d=min(v[0],capacity[phase%3]);v[0]-=d;v[1]+=d
 elif a==2:d=min(v[1],capacity[(phase+1)%3]);v[1]-=d;v[2]+=d
 elif a==3:phase=(phase+1)%4;capacity=capacity[1:]+capacity[:1]
 elif a==4:tests=tests+((tuple(v),phase,tuple(capacity),v[2]>=5),)
 elif a==5:commit=(tuple(v),phase,tuple(capacity),tests[-3:],sum(v))
 return tuple(v),phase,tuple(capacity),tests,commit
for x in LEVELS:
 s=((8,0,0),0,(1,2,3),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for i,v in enumerate(g.mass):x=8+i*18;f[8:31,x:x+13]=TOWER;f[27-v*2:29,x+2:x+11]=MASS;f[10:14,x+3:x+10]=FLAG
  for i,c in enumerate(g.capacity):x=9+i*17;f[35:41,x:x+12]=BEAM;f[42:45,x:x+2+c*3]=CAPACITY
  for i,t in enumerate(g.tests[-3:]):f[48:52,8+i*14:18+i*14]=FLAG if t[3] else BEAM
  f[55:59,8:8+g.phase*11+8]=CAPACITY
  if g.commit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q732(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q732",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.mass=(8,0,0);self.phase=0;self.capacity=(1,2,3);self.tests=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.mass,self.phase,self.capacity,self.tests,self.commit=advance((self.mass,self.phase,self.capacity,self.tests,self.commit),a)
  elif a==6:
   if (self.mass,self.phase,self.capacity,self.tests,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
