"""q542 Lockwater Lesson -- infer a conditional policy despite ineffective gestures."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANAL,BARGE,WATER,CONTEXT,NOISE,RESULT,BAD=6,10,9,12,15,8,14,3
LEVELS=[
 {"name":"Ignore the Gesture","maps":[[1,2,3,4],[2,1,4,3]],"demo":[[1,0,1],[4,0,0],[2,1,1]]},
 {"name":"Context Switch","maps":[[2,3,4,1],[4,3,2,1]],"demo":[[3,0,1],[1,1,1],[2,1,0],[4,0,1]]},
 {"name":"Conditional Policy","maps":[[3,1,4,2],[2,4,1,3]],"demo":[[2,1,1],[4,0,1],[1,0,0],[3,1,1]]},
 {"name":"Identity Not Appearance","maps":[[4,2,1,3],[3,1,2,4]],"demo":[[1,0,1],[2,1,0],[4,1,1],[3,0,1],[2,1,1]]},
 {"name":"Causal Demonstration","maps":[[2,4,3,1],[1,3,4,2]],"demo":[[4,1,1],[3,0,1],[1,1,0],[2,0,1],[1,1,1],[3,0,1]]},
 {"name":"Lockwater Lesson","maps":[[3,4,1,2],[4,1,3,2]],"demo":[[2,0,1],[1,1,1],[4,0,0],[3,1,1],[4,0,1],[2,1,0],[1,0,1]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=CANAL;f[15:28,8:22]=BARGE;f[15:28,42:56]=BARGE;f[31:36,8:56]=WATER
  for i,d in enumerate(g.demo):x=8+i*7;f[42:48,x:x+5]=NOISE if not d[2] else CONTEXT;f[50:54,x:x+5]=RESULT if i<len(g.result) else CANAL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q542(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.maps=self.demo=self.target=self.result=[];self.observed=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q542",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.maps=[list(x) for x in s["maps"]];self.demo=[list(x) for x in s["demo"]];self.target=[x[0] for x in self.demo if x[2]];self.result=[];self.observed=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==5:self.observed=min(len(self.demo),self.observed+1)
  elif z in (1,2,3,4):
   if self.observed<len(self.demo) or len(self.result)>=len(self.target):self.failed=True;self.lose()
   else:
    context=[x[1] for x in self.demo if x[2]][len(self.result)];self.result.append(self.maps[context][z-1])
  elif z==6:
   if self.result==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
