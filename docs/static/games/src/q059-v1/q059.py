"""q059 Sieve -- construct a mesh that filters correctly in both flow directions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TANK,BAR,GAP,SMALL,LARGE,FLOW,CURSOR,BAD=10,0,3,12,9,14,6,11,8
LEVELS=[
 {"name":"Pass Small","target":[2,2],"tests":1}, {"name":"Retain Large","target":[1,2,1],"tests":1},
 {"name":"Mixed Mesh","target":[2,1,3,1],"tests":1}, {"name":"Reverse Flow","target":[1,3,2,1,2],"tests":2},
 {"name":"Survive Reversal","target":[2,1,3,2,1,2],"tests":2}, {"name":"Sieve","target":[1,2,3,1,3,2,1],"tests":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TANK
  for i,v in enumerate(g.gaps):x=7+i*7;f[18:43,x:x+5]=BAR;f[29-v*3:30+v*3,x:x+5]=GAP;f[13:16,x:x+5]=CURSOR if i==g.cursor else TANK
  f[46:50,8:18]=SMALL;f[46:54,45:56]=LARGE;f[3:6,8:8+g.done*18]=FLOW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q059(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.gaps=[];self.tests=self.cursor=self.done=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q059",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.target=list(s["target"]);self.gaps=[1]*len(self.target);self.tests=s["tests"];self.cursor=self.done=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.gaps[self.cursor]=self.gaps[self.cursor]%3+1
  elif z==2:self.gaps[self.cursor]=(self.gaps[self.cursor]-2)%3+1
  elif z==3:self.cursor=(self.cursor-1)%len(self.gaps)
  elif z==4:self.cursor=(self.cursor+1)%len(self.gaps)
  elif z==5:
   if self.gaps==self.target:self.done+=1
   else:self.failed=True;self.lose()
  elif z==6:
   if self.gaps==self.target and self.done>=self.tests:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
