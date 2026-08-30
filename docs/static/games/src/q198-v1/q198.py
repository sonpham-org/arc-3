"""q198 Action Chunking -- reuse a familiar routine inside a novel surrounding plan."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,ACTION,MACRO,NEW,DONE,TARGET,BAD=2,7,9,14,12,10,15,8
MACRO_SEQ=[1,2,3]
LEVELS=[
 {"name":"Learn the Chunk","target":[1,2,3]}, {"name":"Chunk Then New","target":[1,2,3,4]},
 {"name":"New Prefix","target":[4,1,2,3]}, {"name":"Embedded Routine","target":[2,4,1,2,3,1]},
 {"name":"Do Not Copy Suffix","target":[3,1,2,3,4,2]}, {"name":"Action Chunking","target":[4,2,1,2,3,1,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=STAGE;f[14:20,8:30]=MACRO
  for i,t in enumerate(g.target):x=8+i*7;f[31:38,x:x+5]=DONE if i<len(g.result) else TARGET;f[43:48,x:x+5]=ACTION if t in MACRO_SEQ else NEW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q198(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.result=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q198",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.target=list(LEVELS[self.level_index]["target"]);self.result=[];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):self.result.append(z)
  elif z==5:self.result.extend(MACRO_SEQ)
  elif z==6:
   if self.result==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
