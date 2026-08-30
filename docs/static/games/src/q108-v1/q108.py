"""q108 Camera Relative -- controls rotate with the camera while dynamics remain world-relative."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,BODY,GOAL,CAMERA,DRIFT,TRAIL,BAD=10,1,9,14,15,12,6,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)};W=H=6
LEVELS=[
 {"name":"Rotate the View","start":(0,5),"goal":(5,5),"drift":(0,0)},
 {"name":"World Drift","start":(0,4),"goal":(5,1),"drift":(1,0)},
 {"name":"Camera Controls","start":(1,5),"goal":(4,0),"drift":(0,-1)},
 {"name":"Separate Frames","start":(0,3),"goal":(5,2),"drift":(1,0)},
 {"name":"Moving Camera","start":(2,5),"goal":(5,0),"drift":(1,0)},
 {"name":"Camera Relative","start":(0,5),"goal":(5,0),"drift":(0,-1)}]
def rotate(v,r):
 x,y=v
 for _ in range(r):x,y=-y,x
 return x,y
def advance(pos,action,rotation,drift,goal):
 dx,dy=rotate(DIRS[action],rotation);n=(max(0,min(W-1,pos[0]+dx)),max(0,min(H-1,pos[1]+dy)))
 if n==goal:return n
 return(max(0,min(W-1,n[0]+drift[0])),max(0,min(H-1,n[1]+drift[1])))
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[11+y*8:18+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:57,4:60]=FIELD
  for p in g.trail:self.cell(f,p,TRAIL)
  self.cell(f,g.goal,GOAL);self.cell(f,g.pos,BODY);f[3:6,8+g.rotation*12:18+g.rotation*12]=CAMERA;f[59:62,8:8+(abs(g.drift[0])+abs(g.drift[1])+1)*8]=DRIFT
  if g.failed:f[61:64,25:39]=BAD
  return f
class Q108(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.pos=self.goal=self.drift=(0,0);self.rotation=0;self.trail=[];self.budget=40;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q108",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.pos=tuple(s["start"]);self.goal=tuple(s["goal"]);self.drift=tuple(s["drift"]);self.rotation=0;self.trail=[];self.budget=40;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  self.budget-=1
  if z==5:self.rotation=(self.rotation+1)%4
  elif z in DIRS:self.trail.append(self.pos);self.pos=advance(self.pos,z,self.rotation,self.drift,self.goal)
  if self.pos==self.goal:self.next_level()
  elif self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
