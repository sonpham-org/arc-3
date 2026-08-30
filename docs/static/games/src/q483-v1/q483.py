"""q483 Murmuration Dependency -- satisfy a reusable flock DAG and parity audit."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,AVIARY,BIRD,WAKE,DONE,PARITY,CURSOR,BAD=2,7,13,10,15,14,6,8
LEVELS=[
 {"name":"Nested Flock","deps":[[],[0],[0]],"signals":[1,0,1],"mislead":1,"rewire":1},
 {"name":"Shared Wake","deps":[[],[0],[0],[1,2]],"signals":[0,1,1,0],"mislead":2,"rewire":2},
 {"name":"Misleading Bird","deps":[[],[0],[1],[0],[2,3]],"signals":[1,1,0,1,0],"mislead":3,"rewire":2},
 {"name":"Parity Relation","deps":[[],[],[0,1],[1],[2,3]],"signals":[0,1,0,1,1],"mislead":0,"rewire":3},
 {"name":"Reused Marker","deps":[[],[0],[0],[1,2],[2],[3,4]],"signals":[1,0,1,1,0,1],"mislead":4,"rewire":3},
 {"name":"Murmuration Dependency","deps":[[],[],[0],[0,1],[2,3],[1,4]],"signals":[1,1,0,1,0,0],"mislead":2,"rewire":3}]
def parity(l):return sum(v^(i==l["mislead"]) for i,v in enumerate(l["signals"]))%2
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=AVIARY
  for i in range(len(l["deps"])):x=7+i*8;f[16:25,x:x+6]=DONE if g.done&(1<<i) else BIRD
  f[32:37,8:56]=WAKE;f[43:48,8:8+g.claim*18]=PARITY;f[51:56,7+g.cursor*8:13+g.cursor*8]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q483(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.done=self.cursor=self.completed=self.claim=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q483",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):self.done=self.cursor=self.completed=self.claim=0;self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index];n=len(l["deps"])
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%n
  elif z==2:self.cursor=(self.cursor+(2 if self.completed>=l["rewire"] else 1))%n
  elif z==3:self.claim=1-self.claim
  elif z==5 and not self.done&(1<<self.cursor) and all(self.done&(1<<d) for d in l["deps"][self.cursor]):self.done|=1<<self.cursor;self.completed+=1
  elif z==6:
   if self.done==(1<<n)-1 and self.claim==parity(l):self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
