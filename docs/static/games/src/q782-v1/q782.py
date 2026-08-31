"""q782 Lockwater Rhythm -- interrupt coupled water clocks while barges exchange identity cues."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,FAST,SLOW,IDENTITY,GOAL,BAD=9,1,14,10,6,12,11,13,15
LEVELS=[
 {"name":"Barge Tick","seq":(1,)},{"name":"Lock Cycle","seq":(1,1,2)},
 {"name":"Identity Pulse","seq":(3,1,2,1)},{"name":"Coupled Window","seq":(1,2,1,3,2)},
 {"name":"Macro Exchange","seq":(2,1,3,1,2,1,1)},
 {"name":"Lockwater Rhythm","seq":(1,2,3,1,1,2,1,3,2,1,1)}]
def advance(s,a):
 fast,slow,identities,levels,ticks,interrupted=s;i=list(identities);w=list(levels)
 if a==1:
  fast=(fast+1)%4;ticks+=1;w[0]=(w[0]+1)%5
  if fast==0:slow=(slow+1)%5;w=w[1:]+w[:1]
 elif a==2:fast=(fast+2)%4;slow=(slow+1)%5;ticks+=2;i[0],i[1]=i[1],i[0]
 elif a==3:i=i[1:]+i[:1];w=w[-1:]+w[:-1]
 elif a==4:fast=slow=0;w[:]=[1,2,3];ticks+=1
 elif a==5:interrupted=(fast,slow,tuple(i),tuple(w),ticks)
 return fast,slow,tuple(i),tuple(w),ticks,interrupted
for x in LEVELS:
 s=(0,0,(0,1,2),(1,2,3),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CANAL
  for slot,(identity,level) in enumerate(zip(g.identities,g.levels)):
   x=8+slot*17;f[9:31,x:x+13]=WATER;f[26-level*4:30,x+2:x+11]=BARGE;f[33+identity:36+identity,x:x+13]=IDENTITY
  f[43:47,8:8+g.fast*12+8]=FAST;f[50:54,8:8+g.slow*9+7]=SLOW
  if g.interrupted:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q782(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"]
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q782",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.fast=self.slow=self.ticks=0;self.identities=(0,1,2);self.levels=(1,2,3);self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.fast,self.slow,self.identities,self.levels,self.ticks,self.interrupted=advance((self.fast,self.slow,self.identities,self.levels,self.ticks,self.interrupted),a)
  elif a==6:
   if (self.fast,self.slow,self.identities,self.levels,self.ticks,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
