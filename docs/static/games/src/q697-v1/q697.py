"""q697 Catalyst Evidence -- stop when unequal-reliability evidence cannot change the leader."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,PIPE,SAMPLE,SCORE,CURSOR,MEMORY,BAD=11,4,9,15,10,14,6,8
LEVELS=[
 {"name":"Unequal Reliability","samples":[[0,3],[1,1],[0,2]]},
 {"name":"Best Supported","samples":[[1,2],[0,1],[1,3],[0,1]]},
 {"name":"Remaining Evidence","samples":[[0,2],[1,1],[0,4],[1,1]]},
 {"name":"Safe Stopping","samples":[[1,3],[0,2],[1,2],[0,1],[1,3]]},
 {"name":"Write Then Execute","samples":[[0,1],[1,2],[0,5],[1,1],[0,2]]},
 {"name":"Catalyst Evidence","samples":[[1,2],[0,1],[1,4],[0,2],[1,3],[0,1]]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=REFINERY;f[15:29,8:22]=PIPE;f[15:29,42:56]=PIPE;f[34:39,8:8+g.scores[0]*5]=SCORE;f[41:46,8:8+g.scores[1]*5]=SAMPLE;f[49:53,8+g.cursor*24:28+g.cursor*24]=CURSOR
  if g.memory is not None:f[3:6,8:32]=MEMORY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q697(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.samples=[];self.scores=[0,0];self.index=self.cursor=0;self.memory=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q697",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,5,6])
 def on_set_level(self,l):self.samples=[list(x) for x in LEVELS[self.level_index]["samples"]];self.scores=[0,0];self.index=self.cursor=0;self.memory=None;self.failed=False
 def guaranteed(self):
  remain=sum(w for _,w in self.samples[self.index:]);return abs(self.scores[0]-self.scores[1])>remain
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1 and self.index<len(self.samples):c,w=self.samples[self.index];self.scores[c]+=w;self.index+=1
  elif z==3 and self.memory is None:self.cursor=1-self.cursor
  elif z==5 and self.memory is None:
   if self.guaranteed() and self.cursor==max(range(2),key=lambda i:self.scores[i]):self.memory=self.cursor
   else:self.failed=True;self.lose()
  elif z==6:
   final=[0,0]
   for c,w in self.samples:final[c]+=w
   if self.memory==max(range(2),key=lambda i:final[i]):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
