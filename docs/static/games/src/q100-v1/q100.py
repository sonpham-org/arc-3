"""q100 Recursive Gate -- solve nested parameterized instances before unwinding the outer gate."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HALL,GATE,INNER,PARAM,DONE,CURSOR,BAD=6,1,12,10,14,9,11,8
LEVELS=[
 {"name":"Gate Within Gate","params":[1,2]}, {"name":"Inner Parameter","params":[2,0,1]},
 {"name":"Recursive Pattern","params":[3,1,2,0]}, {"name":"Nested Dependency","params":[1,3,0,2,1]},
 {"name":"Outer Control","params":[2,0,3,1,2,0]}, {"name":"Recursive Gate","params":[3,1,0,2,3,0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=HALL
  for i in range(len(g.params)):
   o=i*3;y0,y1=10+o,54-o;x0,x1=8+o,56-o;c=GATE if i>=g.depth else INNER
   f[y0:y0+2,x0:x1]=c;f[y1-2:y1,x0:x1]=c;f[y0:y1,x0:x0+2]=c;f[y0:y1,x1-2:x1]=c
  f[3:6,8:8+g.current*10]=PARAM;f[58:61,8:8+len(g.chosen)*7]=DONE
  if g.failed:f[61:64,25:39]=BAD
  return f
class Q100(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.params=[];self.chosen=[];self.depth=self.current=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q100",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):self.params=list(LEVELS[self.level_index]["params"]);self.chosen=[];self.depth=self.current=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.current=(self.current-1)%4
  elif z==2:self.current=(self.current+1)%4
  elif z==5:
   if self.depth<len(self.params):self.chosen.append(self.current);self.depth+=1;self.current=0
  elif z==6:
   if self.depth==len(self.params) and self.chosen==self.params:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
