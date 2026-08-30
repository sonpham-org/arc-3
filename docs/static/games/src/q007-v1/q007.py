"""q007 Still Guards -- observation freezes patrols but decays watched gates."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,WALL,PLAYER,GUARD,GATE,GOAL,WATCH,BAD=9,1,3,6,8,12,14,11,13
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=7;H=5
LEVELS=[
 {"name":"Freeze Guard","start":(0,2),"goal":(4,2),"guard":[(2,1),(2,2)],"gate":(3,2),"decay":1,"walls":[]},
 {"name":"Watch the Gate","start":(0,4),"goal":(5,0),"guard":[(2,3),(3,3)],"gate":(3,1),"decay":2,"walls":[(1,3)]},
 {"name":"Trade Attention","start":(0,2),"goal":(6,2),"guard":[(2,1),(3,1),(3,2)],"gate":(4,2),"decay":2,"walls":[(2,3)]},
 {"name":"Patrol Timing","start":(0,0),"goal":(6,4),"guard":[(2,1),(3,1),(4,2),(3,3)],"gate":(4,3),"decay":3,"walls":[(1,1),(5,3)]},
 {"name":"Two Threats","start":(0,4),"goal":(6,0),"guard":[(2,4),(3,3),(4,2),(3,1)],"gate":(5,1),"decay":3,"walls":[(1,3),(4,0)]},
 {"name":"Still Guards","start":(0,2),"goal":(6,2),"guard":[(1,1),(2,1),(3,2),(4,3),(5,3)],"gate":(5,2),"decay":4,"walls":[(2,3),(4,1)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[12+y*9:20+y*9,4+x*8:11+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),FIELD)
  for p in g.walls:self.cell(f,p,WALL)
  if g.health:self.cell(f,g.gate,GATE)
  self.cell(f,g.goal,GOAL);self.cell(f,g.patrol[g.phase],GUARD);self.cell(f,g.pos,PLAYER);f[3:7,7:7+g.health*8]=GATE;f[3:7,48:57]=WATCH if g.watched else WALL
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q007(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=self.gate=(0,0);self.patrol=[];self.phase=self.health=0;self.walls=set();self.watched=False;self.budget=50;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q007",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.gate=tuple(s["gate"]);self.patrol=list(map(tuple,s["guard"]));self.health=s["decay"];self.phase=0;self.walls=set(s["walls"]);self.watched=False;self.budget=50;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a==5:self.watched=not self.watched
  elif a in DIRS:
   dx,dy=DIRS[a];n=(self.pos[0]+dx,self.pos[1]+dy);blocked=self.walls|({self.gate} if self.health else set())
   if 0<=n[0]<W and 0<=n[1]<H and n not in blocked and n!=self.patrol[self.phase]:self.pos=n
  else:self.failed=True;self.lose()
  if self.watched:self.health=max(0,self.health-1)
  else:self.phase=(self.phase+1)%len(self.patrol)
  if self.pos==self.patrol[self.phase]:self.failed=True;self.lose()
  elif self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
