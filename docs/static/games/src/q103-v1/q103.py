"""q103 Nested Compass -- controls pass through two independently rotating frames."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,GRID,PLAYER,GOAL,INNER,OUTER,BAD=2,0,1,6,14,9,12,8
DIRS=((0,-1),(1,0),(0,1),(-1,0));W=6;H=6
LEVELS=[
 {"name":"Inner Turn","start":(0,2),"goal":(4,2),"inner":1,"outer":0,"walls":[],"budget":20},
 {"name":"Outer Turn","start":(1,4),"goal":(4,1),"inner":0,"outer":3,"walls":[(2,3)],"budget":24},
 {"name":"Two Frames","start":(0,0),"goal":(5,4),"inner":1,"outer":2,"walls":[(2,1),(3,3)],"budget":28},
 {"name":"Counter Rotation","start":(0,5),"goal":(5,0),"inner":3,"outer":1,"walls":[(1,4),(3,2)],"budget":30},
 {"name":"Moving Bearings","start":(1,1),"goal":(4,5),"inner":2,"outer":3,"walls":[(2,2),(2,3),(4,3)],"budget":32},
 {"name":"Nested Compass","start":(0,3),"goal":(5,2),"inner":1,"outer":3,"walls":[(1,2),(2,2),(3,3),(4,3)],"budget":36}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*8:17+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:58,5:59]=FIELD
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),GRID)
  for p in g.walls:self.cell(f,p,OUTER)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,PLAYER)
  for rot,c,x in ((g.inner,INNER,20),(g.outer,OUTER,42)):
   dx,dy=DIRS[rot];f[3+dy*2:6+dy*2,x+dx*3:x+4+dx*3]=c
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q103(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.inner=self.outer=self.budget=0;self.walls=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q103",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.inner=s["inner"];self.outer=s["outer"];self.walls=set(s["walls"]);self.budget=s["budget"];self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if 1<=a<=4:
   dx,dy=DIRS[(a-1+self.inner+self.outer)%4];n=(self.pos[0]+dx,self.pos[1]+dy)
   if 0<=n[0]<W and 0<=n[1]<H and n not in self.walls:self.pos=n
  elif a==5:self.inner=(self.inner+1)%4
  elif a==6:self.outer=(self.outer-1)%4
  else:self.failed=True;self.lose()
  if self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
