"""q451 Tapestry Lineage -- track a shuttle ancestor across a mid-pattern graph rewrite."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,THREAD,SHUTTLE,TRAIL,REWIRE,CURSOR,BAD=14,9,12,13,15,10,6,8
LEVELS=[
 {"name":"Causal Thread","ops":[1,2],"ancestor":0},{"name":"Appearance Exchange","ops":[2,1,1],"ancestor":1},
 {"name":"Split Pattern","ops":[1,2,1,2],"ancestor":2},{"name":"Rewired Crossing","ops":[2,2,1,2,1],"ancestor":0},
 {"name":"New Adjacency","ops":[1,1,2,1,2,2],"ancestor":2},{"name":"Tapestry Lineage","ops":[2,1,2,2,1,1,2],"ancestor":1}]
def transform(p,z):
 p=list(p)
 if z==1:p=p[1:]+p[:1]
 else:p[0],p[-1]=p[-1],p[0]
 return tuple(p)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,5:59]=LOOM
  for i,v in enumerate(g.perm):x=9+i*17;f[16:29,x:x+11]=SHUTTLE;f[31:35,x:x+3+v*3]=TRAIL
  f[40:44,8:56]=THREAD
  if g.progress>=g.mid:f[46:50,8:56:2]=REWIRE
  f[52:57,9+g.cursor*17:20+g.cursor*17]=CURSOR
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q451(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.perm=(0,1,2);self.progress=self.mid=self.cursor=self.target=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q451",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];p=(0,1,2)
  for z in x["ops"]:p=transform(p,z)
  self.target=p.index(x["ancestor"]);self.perm=(0,1,2);self.progress=self.cursor=0;self.mid=(len(x["ops"])+1)//2;self.bad=False
 def step(self):
  z=self.action.id.value;x=LEVELS[self.level_index]
  if z==0:self.complete_action();return
  if z in (1,2) and self.progress<len(x["ops"]) and z==x["ops"][self.progress]:self.perm=transform(self.perm,z);self.progress+=1
  elif z==3 and self.progress==len(x["ops"]):self.cursor=(self.cursor+2)%3
  elif z==6:
   if self.progress==len(x["ops"]) and self.cursor==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
