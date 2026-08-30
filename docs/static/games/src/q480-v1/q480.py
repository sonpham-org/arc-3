"""q480 Spore Dependency -- solve shared prerequisites at sparse actor alignments."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,SPORE,DEPENDENCY,ACTORA,ACTORB,DONE,BAD=12,11,9,15,10,14,6,8
LEVELS=[
 {"name":"One Prerequisite","deps":[[],[0]],"mods":[2,3]},
 {"name":"Shared Subgoal","deps":[[],[0],[0]],"mods":[3,4]},
 {"name":"Nested Branches","deps":[[],[0],[0],[1,2]],"mods":[3,5]},
 {"name":"Sparse Meeting","deps":[[],[0],[1],[0],[2,3]],"mods":[4,5]},
 {"name":"Reusable Completion","deps":[[],[0],[0],[1],[1,2],[3,4]],"mods":[5,6]},
 {"name":"Spore Dependency","deps":[[],[0],[0],[1,2],[1],[3,4],[2,5]],"mods":[5,7]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GREENHOUSE;n=len(g.deps)
  for i in range(n):x=7+i*(50//n);f[20:33,x:x+7]=DONE if g.done&(1<<i) else SPORE;f[37:41,x:x+7]=DEPENDENCY if g.deps[i] else GREENHOUSE
  f[45:49,8:8+g.phase[0]*7]=ACTORA;f[50:54,8:8+g.phase[1]*5]=ACTORB;f[3:6,8:8+g.cursor*(50//n)]=DONE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q480(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.deps=[];self.mods=self.phase=[];self.cursor=self.done=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q480",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.deps=[list(x) for x in s["deps"]];self.mods=list(s["mods"]);self.phase=[0,0];self.cursor=self.done=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.cursor=(self.cursor-1)%len(self.deps)
  elif z==2:self.cursor=(self.cursor+1)%len(self.deps)
  elif z==3:self.phase[0]=(self.phase[0]+1)%self.mods[0]
  elif z==4:self.phase[1]=(self.phase[1]+1)%self.mods[1]
  elif z==5:
   ready=all(self.done&(1<<i) for i in self.deps[self.cursor]) and not self.done&(1<<self.cursor)
   if self.phase==[0,0] and ready:self.done|=1<<self.cursor;self.phase=[1%self.mods[0],1%self.mods[1]]
   else:self.failed=True;self.lose()
  elif z==6:
   if self.done==(1<<len(self.deps))-1:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
