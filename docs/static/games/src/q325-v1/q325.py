"""q325 Alloy Survey -- union rotating-frame measurements within a sensor budget."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,LANE,SEEN,NEED,FRAME,BAD=7,2,9,12,10,14,15,8
LEVELS=[
 {"name":"Bounded Slice","n":5,"masks":[3,6,12,17],"budget":2,"plan":[1,2]},
 {"name":"Rotating Frame","n":6,"masks":[5,10,20,33],"budget":2,"plan":[2,4]},
 {"name":"Union of Views","n":6,"masks":[3,12,24,34],"budget":3,"plan":[1,3,2]},
 {"name":"Translated Relation","n":7,"masks":[7,14,28,81],"budget":3,"plan":[4,2,1]},
 {"name":"Sensor Budget","n":8,"masks":[9,34,68,145],"budget":4,"plan":[1,4,2,3]},
 {"name":"Alloy Survey","n":8,"masks":[7,25,98,164],"budget":4,"plan":[3,1,4,2]}]
def rotate(mask,shift,n):return((mask<<shift)|(mask>>(n-shift)))&((1<<n)-1) if shift else mask
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=FOUNDRY
  for i in range(g.n):x=7+i*(50//g.n);f[17:35,x:x+6]=BILLET;f[39:44,x:x+6]=SEEN if g.seen&(1<<i) else LANE;f[47:51,x:x+6]=NEED if g.need&(1<<i) else FOUNDRY
  f[3:6,8:8+g.rotation*6]=FRAME
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q325(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=self.budget=self.used=self.rotation=self.seen=self.need=0;self.masks=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q325",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.masks=list(s["masks"]);self.budget=s["budget"];self.used=self.rotation=self.seen=0;need=0;rot=0
  for a in s["plan"]:need|=rotate(self.masks[a-1],rot,self.n);rot=(rot+1)%self.n
  self.need=need;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):
   if self.used>=self.budget:self.failed=True;self.lose()
   else:self.seen|=rotate(self.masks[z-1],self.rotation,self.n);self.used+=1;self.rotation=(self.rotation+1)%self.n
  elif z==5:self.rotation=(self.rotation+1)%self.n
  elif z==6:
   if (self.seen&self.need)==self.need:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
