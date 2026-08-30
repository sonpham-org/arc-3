"""q096 Subgoal Cache -- store and reuse completed subtask boundaries."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WORKSHOP,TASK,CACHE,READY,DONE,CURSOR,BAD=15,12,3,10,14,6,11,8
LEVELS=[
 {"name":"First Cache","tasks":[1,1]}, {"name":"Reuse Boundary","tasks":[1,2,1]},
 {"name":"Two Subgoals","tasks":[1,2,2,1]}, {"name":"Nested Cache","tasks":[1,2,3,2,1]},
 {"name":"Repeated Assembly","tasks":[1,2,3,1,3,2]}, {"name":"Subgoal Cache","tasks":[1,2,3,4,2,3,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=WORKSHOP
  for i,t in enumerate(g.tasks):x=7+i*8;f[18:29,x:x+6]=DONE if i<g.progress else TASK;f[33:38,x:x+t+1]=CACHE if t in g.cache else READY
  for i in range(4):f[44:48,8+i*11:17+i*11]=CURSOR if i+1==g.cursor else CACHE if i+1 in g.cache else WORKSHOP
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q096(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.tasks=[];self.progress=0;self.cache=set();self.cursor=1;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q096",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):self.tasks=list(LEVELS[self.level_index]["tasks"]);self.progress=0;self.cache=set();self.cursor=1;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=4 if self.cursor==1 else self.cursor-1
  elif a==4:self.cursor=1 if self.cursor==4 else self.cursor+1
  elif a==5:
   if self.cursor==self.tasks[self.progress]:self.cache.add(self.cursor);self.progress+=1
   elif self.tasks[self.progress] in self.cache:self.progress+=1
   else:self.failed=True;self.lose()
   if self.progress==len(self.tasks):self.next_level()
  elif a==6:
   if self.tasks[self.progress] in self.cache:self.progress+=1
   else:self.failed=True;self.lose()
   if self.progress==len(self.tasks):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
