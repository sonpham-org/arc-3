"""q063 Two Rooms One Switch -- coordinate remote geometry across alternating views."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOMA,ROOMB,WALL,PLAYER,SWITCH,GOAL,ACTIVE,BAD=12,1,10,3,6,11,14,9,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=6;H=5
LEVELS=[
 {"name":"Remote Door","a":(0,2),"b":(0,2),"switch":(1,2),"goal":(3,2),"door":(2,2),"walls":[]},
 {"name":"Look Back","a":(0,0),"b":(0,4),"switch":(2,0),"goal":(4,4),"door":(2,4),"walls":[(1,4)]},
 {"name":"Shared State","a":(0,4),"b":(0,0),"switch":(1,3),"goal":(5,0),"door":(3,0),"walls":[(1,0),(2,1)]},
 {"name":"Alternating Rooms","a":(0,1),"b":(0,3),"switch":(3,1),"goal":(5,3),"door":(3,3),"walls":[(1,3),(2,2),(4,2)]},
 {"name":"Remote Corridor","a":(0,4),"b":(0,0),"switch":(4,4),"goal":(5,4),"door":(4,3),"walls":[(1,4),(2,3),(3,2),(4,1)]},
 {"name":"Two Rooms One Switch","a":(0,0),"b":(0,4),"switch":(5,0),"goal":(5,0),"door":(3,2),"walls":[(1,3),(2,3),(3,3),(3,1),(4,1)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[12+y*9:20+y*9,6+x*9:14+x*9]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:59,3:61]=ROOMA if g.active==0 else ROOMB
  for p in g.walls:self.cell(f,p,WALL)
  if not g.on:self.cell(f,g.door,WALL)
  self.cell(f,g.switch,SWITCH);self.cell(f,g.goal,GOAL);self.cell(f,g.pos[g.active],PLAYER);f[2:6,27:37]=ACTIVE if g.active else SWITCH
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q063(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=[(0,0),(0,0)];self.switch=self.goal=self.door=(0,0);self.walls=set();self.active=0;self.on=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q063",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=[tuple(s["a"]),tuple(s["b"])];self.switch=tuple(s["switch"]);self.goal=tuple(s["goal"]);self.door=tuple(s["door"]);self.walls=set(s["walls"]);self.active=0;self.on=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in DIRS:
   dx,dy=DIRS[a];p=self.pos[self.active];n=(p[0]+dx,p[1]+dy);blocked=self.walls|({self.door} if self.active==1 and not self.on else set())
   if 0<=n[0]<W and 0<=n[1]<H and n not in blocked:self.pos[self.active]=n
  elif a==5:self.active=1-self.active
  elif a==6 and self.active==0 and self.pos[0]==self.switch:self.on=not self.on
  else:self.failed=True;self.lose()
  if self.pos[1]==self.goal:self.next_level()
  self.complete_action()
