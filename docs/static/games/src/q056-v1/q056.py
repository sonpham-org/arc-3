"""q056 Magnet Chain -- assemble alternating polar segments into a useful field."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FORGE,NORTH,SOUTH,BLANK,TARGET,CURSOR,BAD=12,1,9,6,3,14,11,8
LEVELS=[
 {"name":"Two Poles","target":[0,1]}, {"name":"Alternating Chain","target":[1,0,1]},
 {"name":"Field Direction","target":[0,1,0,1]}, {"name":"Magnetic Tool","target":[1,0,1,0,1]},
 {"name":"Long Attraction","target":[0,1,0,1,0,1]}, {"name":"Magnet Chain","target":[1,0,1,0,1,0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=FORGE
  for i,v in enumerate(g.values):x=7+i*7;f[22:36,x:x+6]=BLANK if v<0 else NORTH if v==0 else SOUTH;f[17:20,x:x+6]=CURSOR if i==g.cursor else FORGE;f[40:44,x:x+6]=TARGET if g.target[i] else FORGE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q056(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=[];self.values=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q056",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.target=list(LEVELS[self.level_index]["target"]);self.values=[-1]*len(self.target);self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.values)
  elif a==4:self.cursor=(self.cursor+1)%len(self.values)
  elif a in (1,2):self.values[self.cursor]=a-1
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
