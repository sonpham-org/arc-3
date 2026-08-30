"""q037 Hole Count -- transformations vary pixels while topology drives success."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CANVAS,SHAPE,HOLE,TARGET,MARK,BAD=3,7,9,3,14,11,8
LEVELS=[
 {"name":"Ignore Silhouette","start":0,"target":1}, {"name":"Preserve One Hole","start":1,"target":2},
 {"name":"Seal and Punch","start":3,"target":1}, {"name":"Topology Over Area","start":1,"target":4},
 {"name":"Deformed Rings","start":4,"target":2}, {"name":"Hole Count","start":0,"target":5}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=CANVAS
  if g.style%2:f[16:47,10:54]=SHAPE;f[12:51,18:46]=SHAPE
  else:f[13:50,12:52]=SHAPE
  for i in range(g.holes):
   x=17+(i%3)*11+(g.style%2)*2;y=20+(i//3)*14;f[y:y+7,x:x+7]=HOLE
  for i in range(g.target):f[4:7,8+i*9:15+i*9]=TARGET
  f[52:55,7:18]=MARK
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q037(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.holes=self.target=self.style=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q037",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.holes=s["start"];self.target=s["target"];self.style=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,4):self.style=(self.style+1)%4
  elif a==2:self.holes=min(5,self.holes+1);self.style=(self.style+1)%4
  elif a==3:self.holes=max(0,self.holes-1);self.style=(self.style+1)%4
  elif a==6:
   if self.holes==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
