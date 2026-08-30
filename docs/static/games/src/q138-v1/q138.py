"""q138 Command Composition -- concatenate object, direction, and timing primitives."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CONSOLE,OBJECT,DIRECTION,TIMING,COMMAND,DONE,BAD=15,1,9,12,14,10,6,8
LEVELS=[
 {"name":"Two Primitives","commands":[[1,3,1]]}, {"name":"Novel Combination","commands":[[2,4,2],[1,3,2]]},
 {"name":"Three-Part Syntax","commands":[[1,4,1],[2,3,2],[1,3,1]]}, {"name":"Command Sequence","commands":[[2,3,1],[1,4,2],[2,4,1],[1,3,2]]},
 {"name":"Compositional Code","commands":[[1,3,2],[2,4,1],[1,4,1],[2,3,2],[1,3,1]]}, {"name":"Command Composition","commands":[[2,4,2],[1,3,1],[2,3,2],[1,4,1],[2,4,1],[1,3,2]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CONSOLE;f[15:26,8:20]=OBJECT;f[15:26,26:38]=DIRECTION;f[15:26,44:56]=TIMING
  for i in range(len(g.commands)):x=8+i*7;f[42:49,x:x+5]=DONE if i<g.progress else COMMAND
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q138(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.commands=[];self.buffer=[];self.progress=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q138",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):self.commands=[list(x) for x in LEVELS[self.level_index]["commands"]];self.buffer=[];self.progress=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.buffer.append(z)
  elif z==5:
   if self.buffer!=self.commands[self.progress]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.buffer=[]
    if self.progress==len(self.commands):self.next_level()
  self.complete_action()
