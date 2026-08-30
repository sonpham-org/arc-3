"""q107 Folding Map -- hinge folds make distant local edges globally adjacent."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TABLE,PANEL,HINGE,FRONT,BACK,TARGET,CURSOR,BAD=10,1,9,12,14,15,6,11,8
LEVELS=[
 {"name":"One Fold","n":4,"plan":[5]}, {"name":"Move the Hinge","n":5,"plan":[4,5]},
 {"name":"Folded Adjacency","n":6,"plan":[4,4,5,3,5]}, {"name":"Two Scales","n":7,"plan":[4,5,4,4,5]},
 {"name":"Nested Fold","n":8,"plan":[4,4,5,3,3,5,4,5]}, {"name":"Folding Map","n":9,"plan":[4,4,4,5,3,5,4,4,5]}]
def fold(order,hinge):return order[:hinge+1]+list(reversed(order[hinge+1:]))
def derive(level):
 order=list(range(level["n"]));h=0
 for z in level["plan"]:
  if z==3:h=(h-1)%(len(order)-1)
  elif z==4:h=(h+1)%(len(order)-1)
  elif z==5:order=fold(order,h)
 return order
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=TABLE;n=len(g.order)
  for i,v in enumerate(g.order):x=6+i*(53//n);f[20:40,x:x+6]=FRONT if v%2 else BACK;f[14:17,x:x+6]=TARGET if v==g.target[i] else PANEL
  x=9+g.hinge*(53//n);f[42:49,x:x+3]=HINGE;f[50:53,x-2:x+5]=CURSOR
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q107(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.order=self.target=[];self.hinge=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q107",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.order=list(range(s["n"]));self.target=derive(s);self.hinge=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==3:self.hinge=(self.hinge-1)%(len(self.order)-1)
  elif z==4:self.hinge=(self.hinge+1)%(len(self.order)-1)
  elif z==5:self.order=fold(self.order,self.hinge)
  elif z==6:
   if self.order==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
