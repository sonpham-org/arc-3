"""q058 Antenna -- construct oriented conductive spans tuned to a pulsing source."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,HORIZ,VERT,EMPTY,PULSE,POWER,CURSOR,BAD=14,10,12,9,3,15,11,6,8
LEVELS=[
 {"name":"Span","target":[0,0]}, {"name":"Orientation","target":[1,0,1]},
 {"name":"Tuned Length","target":[0,1,0,1]}, {"name":"Remote Gate","target":[1,1,0,1,0]},
 {"name":"Pulse Selection","target":[0,1,1,0,1,0]}, {"name":"Antenna","target":[1,0,1,1,0,1,0]}]
def frequency(pattern):return sum((i+1)*(v+1) for i,v in enumerate(pattern))%8
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SKY
  for i,v in enumerate(g.parts):
   x=7+i*7;f[23:38,x:x+6]=EMPTY if v<0 else HORIZ if v==0 else VERT;f[18:21,x:x+6]=CURSOR if i==g.cursor else SKY
  f[43:47,8:8+g.source*5]=PULSE;f[50:54,45:56]=POWER if g.powered else EMPTY
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q058(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.parts=[];self.source=self.cursor=0;self.powered=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q058",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.target=list(LEVELS[self.level_index]["target"]);self.parts=[-1]*len(self.target);self.source=frequency(self.target);self.cursor=0;self.powered=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):self.parts[self.cursor]=z-1;self.powered=False
  elif z==3:self.cursor=(self.cursor-1)%len(self.parts)
  elif z==4:self.cursor=(self.cursor+1)%len(self.parts)
  elif z==5:self.powered=-1 not in self.parts and frequency(self.parts)==self.source
  elif z==6:
   if self.powered and self.parts==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
