"""q106 Local Gravity Wells -- falling direction changes across visibly oriented regions."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BODY,GOAL,ARROW,BOUNDARY,TRAIL,BAD=2,7,9,14,12,3,10,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W,H=6,5
LEVELS=[
 {"name":"One Gravity","start":(0,4),"goal":(5,4),"gravity":[(0,1)]*6},
 {"name":"Boundary Fall","start":(0,4),"goal":(5,0),"gravity":[(0,1)]*3+[(0,-1)]*3},
 {"name":"Sideways Well","start":(0,2),"goal":(5,0),"gravity":[(1,0),(1,0),(0,1),(0,1),(0,-1),(0,-1)]},
 {"name":"Four Orientations","start":(0,4),"goal":(5,0),"gravity":[(-1,0),(1,0),(0,-1),(1,0),(0,1),(0,-1)]},
 {"name":"Cross the Wells","start":(1,4),"goal":(5,1),"gravity":[(1,0),(0,-1),(0,1),(1,0),(0,-1),(-1,0)]},
 {"name":"Local Gravity Wells","start":(1,4),"goal":(5,0),"gravity":[(0,1),(0,-1),(0,1),(1,0),(0,-1),(-1,0)]}]
def advance(pos,action,gravity,goal):
 dx,dy=DIRS[action];n=(max(0,min(W-1,pos[0]+dx)),max(0,min(H-1,pos[1]+dy)))
 if n==goal:return n
 gx,gy=gravity[n[0]];return(max(0,min(W-1,n[0]+gx)),max(0,min(H-1,n[1]+gy)))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[13+y*8:20+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:57,4:60]=FIELD
  for x,(dx,dy) in enumerate(g.gravity):f[4:7,8+x*8:15+x*8]=ARROW;f[52:55,10+x*8:13+x*8]=ARROW if dy else BOUNDARY
  for p in g.trail:self.cell(f,p,TRAIL)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,BODY)
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q106(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=(0,0);self.gravity=[];self.trail=[];self.budget=40;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q106",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.gravity=list(map(tuple,s["gravity"]));self.trail=[];self.budget=40;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if z in DIRS:self.trail.append(self.pos);self.pos=advance(self.pos,z,self.gravity,self.goal)
  if self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
