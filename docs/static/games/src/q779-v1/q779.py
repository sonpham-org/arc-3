"""q779 Strata Rhythm -- undo the physical probe but retain timing knowledge."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,QUARRY,FAULT,ORE,LOCAL,MACRO,KNOWLEDGE,INTERRUPT,BAD=10,8,11,6,2,9,4,13,15
LEVELS=[
 {"name":"Single Probe","cycle":3,"window":1,"outer":0,"plan":(1,4,5)},
 {"name":"Double Probe","cycle":3,"window":2,"outer":0,"plan":(2,4,5)},
 {"name":"Whole Routine","cycle":3,"window":0,"outer":1,"plan":(3,4,5)},
 {"name":"Restored Window","cycle":4,"window":2,"outer":1,"plan":(3,2,4,5)},
 {"name":"Persistent Timing","cycle":5,"window":1,"outer":2,"plan":(3,3,1,4,5)},
 {"name":"Strata Rhythm","cycle":4,"window":3,"outer":3,"plan":(3,3,3,2,1,4,5)}]
def tick(local,macro,world,knowledge,n,cycle):
 total=local+n;world=(world+n)%4;knowledge|=1<<world;return total%cycle,macro+total//cycle,world,knowledge
def advance(s,a,x):
 local,macro,world,knowledge,interrupted=s
 if a==1:local,macro,world,knowledge=tick(local,macro,world,knowledge,1,x["cycle"])
 elif a==2:local,macro,world,knowledge=tick(local,macro,world,knowledge,2,x["cycle"])
 elif a==3:local,macro,world,knowledge=tick(local,macro,world,knowledge,x["cycle"],x["cycle"])
 elif a==4:world=0
 elif a==5:
  if local!=x["window"] or macro%4!=x["outer"] or not knowledge:return None
  interrupted=(local,macro,world,knowledge)
 return local,macro,world,knowledge,interrupted
def target(x):
 s=(0,0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=QUARRY
  for i in range(4):f[8+i*9:14+i*9,8:56]=FAULT+i%2
  f[10:13,8:8+g.local*10]=LOCAL;f[20:23,8:8+(g.macro%4)*10]=MACRO;f[38:40,8:56]=ORE;f[40:44,8:8+g.world*11]=ORE;f[47:50,8:8+g.knowledge.bit_count()*9]=KNOWLEDGE
  if g.interrupted:f[53:57,39:56]=INTERRUPT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q779(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q779",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.local=self.macro=self.world=self.knowledge=0;self.interrupted=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.local,self.macro,self.world,self.knowledge,self.interrupted),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.local,self.macro,self.world,self.knowledge,self.interrupted=s
  elif a==6:
   if (self.local,self.macro,self.world,self.knowledge,self.interrupted)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
