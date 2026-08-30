"""q090 Lineage Garden -- inspect inherited traits and prune without losing the needed lineage."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,BRANCH,LEAF,TRAIT0,TRAIT1,PRUNED,CURSOR,BAD=11,1,12,10,8,14,3,15,6
LEVELS=[
 {"name":"Inherited Trait","traits":[1,0]}, {"name":"Sibling Branches","traits":[0,1,1]},
 {"name":"Preserve Lineage","traits":[1,0,0,1]}, {"name":"Branch Memory","traits":[0,1,0,1,1]},
 {"name":"Selective Pruning","traits":[1,0,1,0,0,1]}, {"name":"Lineage Garden","traits":[0,1,1,0,1,0,0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GARDEN;n=len(g.traits);f[37:42,8:56]=BRANCH
  for i,t in enumerate(g.traits):x=7+i*(50//n);f[20:37,x:x+4]=BRANCH;f[14:22,x-1:x+6]=PRUNED if i in g.pruned else TRAIT1 if i in g.inspected and t else TRAIT0 if i in g.inspected else LEAF;f[45:49,x-1:x+6]=CURSOR if i==g.cursor else GARDEN
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q090(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.traits=[];self.cursor=0;self.inspected=self.pruned=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q090",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):self.traits=list(LEVELS[self.level_index]["traits"]);self.cursor=0;self.inspected=set();self.pruned=set();self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.inspected.add(self.cursor)
  elif z==3:self.cursor=(self.cursor-1)%len(self.traits)
  elif z==4:self.cursor=(self.cursor+1)%len(self.traits)
  elif z==5:self.pruned.add(self.cursor)
  elif z==6:
   wanted={i for i,t in enumerate(self.traits) if not t}
   if len(self.inspected)==len(self.traits) and self.pruned==wanted:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
