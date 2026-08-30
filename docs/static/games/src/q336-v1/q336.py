"""q336 Backstage Survey -- cover rotating sightlines while accumulating directed influence."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,THEATER,MASK,SIGHT,SEEN,METER,NEED,BAD=10,2,9,12,6,15,14,8
LEVELS=[
 {"name":"Bounded Sightline","n":5,"masks":[3,6,12,17],"delta":[1,-1,2,-2],"budget":2,"plan":[1,3]},
 {"name":"Direction Matters","n":6,"masks":[5,10,20,33],"delta":[2,-1,1,-2],"budget":2,"plan":[2,4]},
 {"name":"Accumulate Influence","n":6,"masks":[3,12,24,34],"delta":[1,2,-1,-2],"budget":3,"plan":[1,3,2]},
 {"name":"Rotating Theater","n":7,"masks":[7,14,28,81],"delta":[2,-2,1,-1],"budget":3,"plan":[4,2,1]},
 {"name":"Threshold Survey","n":8,"masks":[9,34,68,145],"delta":[1,2,3,-2],"budget":4,"plan":[1,4,2,3]},
 {"name":"Backstage Survey","n":8,"masks":[7,25,98,164],"delta":[3,-1,2,-2],"budget":4,"plan":[3,1,4,2]}]
def rotate(mask,shift,n):return((mask<<shift)|(mask>>(n-shift)))&((1<<n)-1) if shift else mask
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=THEATER
  for i in range(g.n):x=7+i*(50//g.n);f[17:33,x:x+6]=MASK;f[37:42,x:x+6]=SEEN if g.seen&(1<<i) else SIGHT;f[45:49,x:x+6]=NEED if g.need&(1<<i) else THEATER
  f[3:6,24:24+max(1,g.meter+12)*2]=METER
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q336(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=self.budget=self.used=self.rotation=self.seen=self.need=self.meter=self.target_meter=0;self.masks=self.delta=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q336",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.budget=s["budget"];self.masks=list(s["masks"]);self.delta=list(s["delta"]);self.used=self.rotation=self.seen=self.meter=0;need=target=0;rot=0
  for a in s["plan"]:need|=rotate(self.masks[a-1],rot,self.n);target+=self.delta[a-1];rot=(rot+1)%self.n
  self.need=need;self.target_meter=target;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3,4):
   if self.used>=self.budget:self.failed=True;self.lose()
   else:self.seen|=rotate(self.masks[z-1],self.rotation,self.n);self.meter+=self.delta[z-1];self.used+=1;self.rotation=(self.rotation+1)%self.n
  elif z==5:self.rotation=(self.rotation+1)%self.n
  elif z==6:
   if (self.seen&self.need)==self.need and self.meter==self.target_meter:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
