"""q104 Conveyor Frame -- compose object, belt, and board motion each tick."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BELT,PLAYER,GOAL,BOARD,BAD=3,1,10,6,14,12,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=7;H=6
LEVELS=[
 {"name":"Belt Drift","start":(0,2),"goal":(5,2),"belt":(1,0),"board":[(0,0)]},
 {"name":"Board Motion","start":(1,4),"goal":(5,1),"belt":(0,0),"board":[(1,0),(0,-1)]},
 {"name":"Two Velocities","start":(0,0),"goal":(6,4),"belt":(1,0),"board":[(0,1),(0,0)]},
 {"name":"Opposed Frames","start":(5,5),"goal":(1,0),"belt":(-1,0),"board":[(0,-1),(1,0)]},
 {"name":"Alternating Board","start":(0,3),"goal":(6,2),"belt":(0,1),"board":[(1,0),(0,-1),(-1,0)]},
 {"name":"Conveyor Frame","start":(3,3),"goal":(0,5),"belt":(1,0),"board":[(0,-1),(-1,0),(0,1)]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*8:17+y*8,5+x*8:12+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:58,2:62]=FIELD
  for y in range(H):
   for x in range(W):self.cell(f,(x,y),BELT if (x+y)%2 else FIELD)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,PLAYER);f[3:6,8+g.t*8:14+g.t*8]=BOARD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q104(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=self.belt=(0,0);self.board=[];self.t=0;self.budget=30;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q104",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.belt=tuple(s["belt"]);self.board=list(map(tuple,s["board"]));self.t=0;self.budget=30;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a in DIRS:
   d=DIRS[a];b=self.board[self.t%len(self.board)];self.pos=((self.pos[0]+d[0]+self.belt[0]+b[0])%W,(self.pos[1]+d[1]+self.belt[1]+b[1])%H);self.t+=1
  else:self.failed=True;self.lose()
  if self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
