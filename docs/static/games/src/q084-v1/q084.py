"""q084 Control Transfer -- contact changes the controlled body, not its attached goal."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,WALL,BODYA,BODYB,GOALA,GOALB,ACTIVE,BAD=9,1,3,6,10,14,12,11,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=6;H=6
LEVELS=[
 {"name":"Touch to Transfer","pos":[(0,2),(2,2)],"goals":[(1,2),(3,2)],"walls":[]},
 {"name":"Separate Goals","pos":[(0,0),(2,1)],"goals":[(1,0),(4,1)],"walls":[]},
 {"name":"Contact Route","pos":[(0,5),(2,4)],"goals":[(1,4),(5,4)],"walls":[(3,3)]},
 {"name":"Body and Objective","pos":[(0,1),(3,2)],"goals":[(2,1),(5,2)],"walls":[(2,2),(4,1)]},
 {"name":"Transfer Maze","pos":[(0,5),(2,3)],"goals":[(1,3),(5,1)],"walls":[(2,4),(3,3),(4,2)]},
 {"name":"Control Transfer","pos":[(0,3),(2,2)],"goals":[(1,2),(5,4)],"walls":[(2,4),(3,1),(4,3)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*8:17+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:58,5:59]=FIELD
  for p in g.walls:self.cell(f,p,WALL)
  self.cell(f,g.goals[0],GOALA);self.cell(f,g.goals[1],GOALB);self.cell(f,g.pos[0],BODYA);self.cell(f,g.pos[1],BODYB);f[3:7,27:37]=ACTIVE+g.active
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q084(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=[];self.goals=[];self.walls=set();self.active=0;self.budget=40;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q084",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=list(map(tuple,s["pos"]));self.goals=list(map(tuple,s["goals"]));self.walls=set(s["walls"]);self.active=0;self.budget=40;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a in DIRS:
   dx,dy=DIRS[a];p=self.pos[self.active];n=(p[0]+dx,p[1]+dy)
   if n==self.pos[1-self.active]:self.active=1-self.active
   elif 0<=n[0]<W and 0<=n[1]<H and n not in self.walls:self.pos[self.active]=n
  elif a==6:
   if self.pos==self.goals:self.next_level()
   else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
