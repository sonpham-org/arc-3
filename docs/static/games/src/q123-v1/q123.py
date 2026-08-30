"""q123 Last-Move Guard -- a guard blocks repetition of the last successful direction."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,WALL,PLAYER,GOAL,GUARD,TRAIL,BAD=0,10,3,6,14,8,11,13
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=6;H=6
LEVELS=[
 {"name":"Do Not Repeat","start":(0,0),"goal":(2,1),"walls":[]},
 {"name":"Alternating Path","start":(0,5),"goal":(3,2),"walls":[(2,4)]},
 {"name":"Guarded Corridor","start":(0,2),"goal":(5,2),"walls":[(2,1),(3,3)]},
 {"name":"Adaptive Detour","start":(5,5),"goal":(0,0),"walls":[(2,4),(3,2)]},
 {"name":"Patrol Memory","start":(0,0),"goal":(5,5),"walls":[(1,2),(2,2),(4,3)]},
 {"name":"Last-Move Guard","start":(0,3),"goal":(5,2),"walls":[(1,1),(2,3),(3,2),(4,4)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*8:17+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:58,5:59]=FIELD
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),TRAIL)
  for p in g.walls:self.cell(f,p,WALL)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,PLAYER)
  if g.last:self.cell(f,(g.last-1,0),GUARD)
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q123(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.walls=set();self.last=0;self.budget=24;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q123",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.walls=set(s["walls"]);self.last=0;self.budget=24+self.level_index*4;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a not in DIRS:self.failed=True;self.lose()
  elif a!=self.last:
   dx,dy=DIRS[a];n=(self.pos[0]+dx,self.pos[1]+dy)
   if 0<=n[0]<W and 0<=n[1]<H and n not in self.walls:self.pos=n;self.last=a
  if self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
