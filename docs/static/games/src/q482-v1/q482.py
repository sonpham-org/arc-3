"""q482 Lockwater Dependency -- solve reusable canal prerequisites after identity exchange."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,DONE,IDENTITY,CURSOR,BAD=14,9,12,10,15,13,6,8
LEVELS=[
 {"name":"Nested Request","deps":[[],[0],[0]],"gains":[1,2,1],"mod":3,"rewire":1},
 {"name":"Shared Lock","deps":[[],[0],[0],[1,2]],"gains":[2,1,2,1],"mod":4,"rewire":2},
 {"name":"Identity Exchange","deps":[[],[0],[1],[0],[2,3]],"gains":[1,3,2,1,2],"mod":5,"rewire":2},
 {"name":"Coupled Water","deps":[[],[],[0,1],[1],[2,3]],"gains":[2,1,3,2,1],"mod":6,"rewire":3},
 {"name":"Reused Subgoal","deps":[[],[0],[0],[1,2],[2],[3,4]],"gains":[1,2,1,3,2,1],"mod":7,"rewire":3},
 {"name":"Lockwater Dependency","deps":[[],[],[0],[0,1],[2,3],[1,4]],"gains":[2,3,1,2,3,1],"mod":8,"rewire":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;l=LEVELS[g.level_index];f[:,:]=BG;f[5:59,4:60]=CANAL
  for i in range(len(l["deps"])):x=7+i*8;f[16:25,x:x+6]=DONE if g.done&(1<<i) else BARGE
  f[31:36,8:8+g.water*6]=WATER;f[41:46,8:8+sum(g.perm)*4]=IDENTITY;f[50:55,7+g.cursor*8:13+g.cursor*8]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q482(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.done=self.cursor=self.completed=self.water=0;self.perm=[];self.ever=False;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q482",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):n=len(LEVELS[self.level_index]["deps"]);self.done=self.cursor=self.completed=self.water=0;self.perm=list(range(n));self.ever=self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value;l=LEVELS[self.level_index];n=len(l["deps"])
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%n
  elif z==2:self.cursor=(self.cursor+(2 if self.completed>=l["rewire"] else 1))%n
  elif z==3:self.perm[0],self.perm[1]=self.perm[1],self.perm[0];self.ever=True
  elif z==5 and not self.done&(1<<self.cursor) and all(self.done&(1<<d) for d in l["deps"][self.cursor]) and (self.cursor!=0 or self.perm[0]==1):self.done|=1<<self.cursor;self.completed+=1;self.water=(self.water+l["gains"][self.cursor])%l["mod"]
  elif z==6:
   if self.done==(1<<n)-1 and self.ever and self.water==sum(l["gains"])%l["mod"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
