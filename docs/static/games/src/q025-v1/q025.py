"""q025 Latent Gearbox -- interventions reveal hidden clutch transmission."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,GEAR,DRIVEN,TARGET,CURSOR,BAD=13,0,1,9,14,11,8
LEVELS=[
 {"name":"One Clutch","start":[0,0],"target":[1,1],"links":[[0,1],[1]]}, {"name":"Hidden Contact","start":[0,0,0],"target":[1,0,1],"links":[[0,2],[1],[2]]},
 {"name":"Gear Branch","start":[0,0,0],"target":[1,1,0],"links":[[0,1],[1,2],[2]]}, {"name":"Distant Drive","start":[0,0,0,0],"target":[1,0,1,0],"links":[[0,2],[1,3],[2],[3]]},
 {"name":"Clutch Network","start":[0,0,0,0],"target":[1,1,1,0],"links":[[0,1],[1,2],[2,3],[3]]}, {"name":"Latent Gearbox","start":[0,0,0,0,0],"target":[1,0,1,1,0],"links":[[0,2],[1,4],[2,3],[3,4],[4]]}]
def turn(vals,links,i):
 o=list(vals)
 for j in links[i]:o[j]=1-o[j]
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=SHOP;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=9+i*(47//n);f[22:35,x:x+10]=DRIVEN if v else GEAR;f[15:18,x:x+10]=TARGET if t else SHOP;f[39:43,x:x+10]=CURSOR if i==g.cursor else SHOP
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q025(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.links=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q025",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.links=[list(x) for x in s["links"]];self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.values)
  elif a==4:self.cursor=(self.cursor+1)%len(self.values)
  elif a==5:self.values=turn(self.values,self.links,self.cursor)
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
