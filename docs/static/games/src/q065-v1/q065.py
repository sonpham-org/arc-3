"""q065 Asymmetric Twins -- alternate color-only and shape-only observers to classify objects."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,COLOR,SHAPE,TWIN,VALID,DONE,BAD=14,1,9,12,10,6,11,8
LEVELS=[
 {"name":"Two Views","items":[(1,1),(2,1)]}, {"name":"Alternate Twins","items":[(1,2),(2,2),(3,1)]},
 {"name":"Joint Evidence","items":[(3,3),(1,2),(2,2),(3,1)]}, {"name":"Hidden Attribute","items":[(1,3),(2,1),(3,3),(2,2),(1,1)]},
 {"name":"Shared Decision","items":[(3,2),(1,1),(2,3),(2,2),(1,3),(3,3)]}, {"name":"Asymmetric Twins","items":[(1,2),(2,1),(3,3),(1,1),(3,2),(2,2),(1,3)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=ROOM
  for i,(c,s) in enumerate(g.items):x=7+i*8;f[18:27,x:x+6]=COLOR+c if g.twin==0 else SHAPE;f[20:24,x:x+s+1]=TWIN;f[39:46,x:x+6]=DONE if i<g.progress else VALID
  f[3:6,27:37]=COLOR if g.twin==0 else SHAPE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q065(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.items=[];self.progress=self.twin=0;self.seen_color=True;self.seen_shape=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q065",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5])
 def on_set_level(self,l):self.items=list(map(tuple,LEVELS[self.level_index]["items"]));self.progress=self.twin=0;self.seen_color=True;self.seen_shape=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==5:self.twin=1-self.twin;self.seen_color|=self.twin==0;self.seen_shape|=self.twin==1
  elif a in (1,2):
   expected=1 if self.items[self.progress][0]==self.items[self.progress][1] else 2
   if not(self.seen_color and self.seen_shape) or a!=expected:self.failed=True;self.lose()
   else:
    self.progress+=1;self.seen_color=self.twin==0;self.seen_shape=self.twin==1
    if self.progress==len(self.items):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
