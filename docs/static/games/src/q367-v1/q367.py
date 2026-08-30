"""q367 Catalyst Rig -- build a device whose observed orientation executes when hidden."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,REFINERY,SLOT,REDIRECT,JOIN,SUPPORT,MEMORY,BAD=11,4,12,9,10,14,6,8
LEVELS=[
 {"name":"Redirect and Remember","target":[1,2,1],"cursor":1},{"name":"Joined Orientation","target":[2,1,3],"cursor":2},
 {"name":"Support Geometry","target":[3,1,2,1],"cursor":0},{"name":"Hidden Execution","target":[1,3,2,2],"cursor":2},
 {"name":"Reusable Device","target":[2,3,1,2,1],"cursor":1},{"name":"Catalyst Rig","target":[3,2,1,3,2],"cursor":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=REFINERY;n=len(g.slots)
  for i,v in enumerate(g.slots):x=8+i*(48//n);f[18:35,x:x+8]=SLOT if not v else (REDIRECT,JOIN,SUPPORT)[v-1];f[41:45,x:x+8]=MEMORY if i==g.cursor else REFINERY
  if g.memory is not None:f[3:6,8:32]=MEMORY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q367(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.slots=[];self.cursor=self.memory_cursor=0;self.memory=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q367",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.slots=[0]*len(self.target);self.memory_cursor=s["cursor"];self.cursor=0;self.memory=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3) and self.memory is None:self.slots[self.cursor]=z
  elif z==4 and self.memory is None:self.cursor=(self.cursor+1)%len(self.slots)
  elif z==5 and self.memory is None:
   if self.slots==self.target and self.cursor==self.memory_cursor:self.memory=self.slots[self.cursor];self.slots=self.slots[self.memory:]+self.slots[:self.memory]
   else:self.failed=True;self.lose()
  elif z==6:
   expected=self.target[(self.target[self.memory_cursor] if self.memory is not None else 0):]+self.target[:(self.target[self.memory_cursor] if self.memory is not None else 0)]
   if self.memory is not None and self.slots==expected:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
