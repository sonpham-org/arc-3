"""q491 Pollen Dependency -- solve a prerequisite graph across a visible rule complement."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,POLLEN,BLOOM,WEAR,DEPENDENCY,DONE,BAD=15,7,9,14,10,12,6,8
LEVELS=[
 {"name":"One Dependency","deps":[[],[0]],"wear":1},{"name":"Shared Bloom","deps":[[],[0],[0]],"wear":1},
 {"name":"Rule Complement","deps":[[],[0],[0],[1,2]],"wear":2},{"name":"Nested Request","deps":[[],[0],[1],[0],[2,3]],"wear":2},
 {"name":"Reusable Subgoal","deps":[[],[0],[0],[1],[1,2],[3,4]],"wear":3},{"name":"Pollen Dependency","deps":[[],[0],[0],[1,2],[1],[3,4],[2,5]],"wear":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MEADOW;n=len(g.deps)
  for i in range(n):x=7+i*(50//n);f[19:33,x:x+7]=DONE if g.done&(1<<i) else POLLEN;f[37:41,x:x+7]=DEPENDENCY if g.deps[i] else MEADOW
  f[45:49,8:30]=WEAR if g.completed>=g.wear else BLOOM;f[3:6,8:8+g.cursor*(50//n)]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q491(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.deps=[];self.wear=self.completed=self.cursor=self.done=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q491",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.deps=[list(x) for x in s["deps"]];self.wear=s["wear"];self.completed=self.cursor=self.done=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%len(self.deps)
  elif z==2:self.cursor=(self.cursor+1)%len(self.deps)
  elif z in (4,5):
   expected=4 if self.completed<self.wear else 5;ready=all(self.done&(1<<i) for i in self.deps[self.cursor]) and not self.done&(1<<self.cursor)
   if z==expected and ready:self.done|=1<<self.cursor;self.completed+=1
   else:self.failed=True;self.lose()
  elif z==6:
   if self.done==(1<<len(self.deps))-1:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
