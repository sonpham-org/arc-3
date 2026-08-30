"""q073 Phase Change -- accumulate heat to revise the traversal rule."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SOLID,FLUID,PLAYER,GOAL,HEAT,BAD=11,0,10,9,6,14,12,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=6;H=5
LEVELS=[
 {"name":"Melt Gate","start":(0,2),"goal":(3,2),"material":[(2,2)],"walls":[],"threshold":1},
 {"name":"Heat First","start":(0,4),"goal":(4,0),"material":[(2,2),(3,1)],"walls":[(1,3)],"threshold":2},
 {"name":"Solid Detour","start":(0,2),"goal":(5,2),"material":[(2,2),(3,2)],"walls":[(2,1),(3,3)],"threshold":3},
 {"name":"Phase Boundary","start":(0,0),"goal":(5,4),"material":[(1,1),(2,2),(3,3)],"walls":[(1,0),(4,3)],"threshold":2},
 {"name":"Energy Ledger","start":(0,4),"goal":(5,0),"material":[(1,3),(2,2),(3,1),(4,0)],"walls":[(2,3),(3,2)],"threshold":4},
 {"name":"Phase Change","start":(0,2),"goal":(5,2),"material":[(1,2),(2,2),(3,2),(4,2)],"walls":[(1,1),(2,3),(3,1),(4,3)],"threshold":5}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[12+y*9:20+y*9,5+x*9:13+x*9]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),FIELD)
  for p in g.walls:self.cell(f,p,SOLID)
  for p in g.material:self.cell(f,p,FLUID if g.energy>=g.threshold else SOLID)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,PLAYER);f[3:7,5:5+min(g.energy,10)*5]=HEAT
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q073(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.material=self.walls=set();self.threshold=self.energy=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q073",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.material=set(s["material"]);self.walls=set(s["walls"]);self.threshold=s["threshold"];self.energy=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in DIRS:
   dx,dy=DIRS[a];n=(self.pos[0]+dx,self.pos[1]+dy);blocked=self.walls|(self.material if self.energy<self.threshold else set())
   if 0<=n[0]<W and 0<=n[1]<H and n not in blocked:self.pos=n
  elif a==5:self.energy+=1
  else:self.failed=True;self.lose()
  if self.pos==self.goal:self.next_level()
  self.complete_action()
