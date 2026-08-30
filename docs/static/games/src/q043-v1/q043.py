"""q043 Sampling Cart -- spend finite samples before traversing heterogeneous ground."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SOIL,HIDDEN,SAFE,ROCK,CART,GOAL,SAMPLE,BAD=13,12,3,14,8,9,6,11,5
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=6;H=5
LEVELS=[
 {"name":"First Sample","start":(0,2),"goal":(2,2),"rocks":[],"samples":2},
 {"name":"Forked Soil","start":(0,2),"goal":(4,2),"rocks":[(2,2)],"samples":6},
 {"name":"Sparse Core","start":(0,0),"goal":(5,4),"rocks":[(2,0),(2,1),(4,3)],"samples":9},
 {"name":"Sampling Budget","start":(0,4),"goal":(5,0),"rocks":[(1,3),(2,3),(3,1),(4,1)],"samples":9},
 {"name":"Material Channel","start":(0,2),"goal":(5,2),"rocks":[(1,1),(2,2),(3,2),(4,3)],"samples":9},
 {"name":"Sampling Cart","start":(0,0),"goal":(5,4),"rocks":[(1,0),(1,2),(2,2),(3,1),(3,3),(4,3)],"samples":10}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*9:18+y*9,5+x*9:13+x*9]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),ROCK if (x,y) in g.revealed and (x,y) in g.rocks else SAFE if (x,y) in g.revealed else HIDDEN)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,CART);f[3:6,5:5+g.samples*4]=SAMPLE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q043(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.rocks=self.revealed=set();self.samples=0;self.facing=4;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q043",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.rocks=set(s["rocks"]);self.revealed={self.pos,self.goal};self.samples=s["samples"];self.facing=4;self.failed=False
 def ahead(self):dx,dy=DIRS[self.facing];return self.pos[0]+dx,self.pos[1]+dy
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in DIRS:
   self.facing=a;n=self.ahead()
   if n in self.revealed and n not in self.rocks and 0<=n[0]<W and 0<=n[1]<H:self.pos=n
  elif a==5:
   n=self.ahead()
   if self.samples and 0<=n[0]<W and 0<=n[1]<H:self.samples-=1;self.revealed.add(n)
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.pos==self.goal:self.next_level()
  self.complete_action()
