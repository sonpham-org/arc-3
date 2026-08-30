"""q148 Delayed Commit -- queue and preview a path before one irreversible execution."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GRID,START,GOAL,QUEUE,PREVIEW,COMMIT,BAD=14,1,9,12,15,10,6,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"Queue Then Commit","start":(1,1),"route":[4,2]}, {"name":"Inspect the Path","start":(0,3),"route":[4,4,1]},
 {"name":"One Preview","start":(2,4),"route":[1,4,1,3]}, {"name":"Delayed Choice","start":(0,4),"route":[4,1,4,1,4]},
 {"name":"Whole-Path Risk","start":(4,4),"route":[3,1,3,1,4,1]}, {"name":"Delayed Commit","start":(0,4),"route":[4,4,1,3,1,4,1]}]
def endpoint(start,route):
 x,y=start
 for a in route:dx,dy=DIRS[a];x=max(0,min(5,x+dx));y=max(0,min(5,y+dy))
 return x,y
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def cell(self,f,p,c):x,y=p;f[10+y*8:17+y*8,8+x*8:15+x*8]=c
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:57,4:60]=GRID;self.cell(f,g.start,START);self.cell(f,g.goal,GOAL)
  if g.preview:self.cell(f,g.preview_pos,PREVIEW)
  f[3:6,8:8+len(g.queue)*6]=QUEUE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q148(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.start=self.goal=self.preview_pos=(0,0);self.route=self.queue=[];self.preview=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q148",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.start=tuple(s["start"]);self.route=list(s["route"]);self.goal=endpoint(self.start,self.route);self.preview_pos=self.start;self.queue=[];self.preview=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in DIRS:self.queue.append(z);self.preview=False
  elif z==5:self.preview_pos=endpoint(self.start,self.queue);self.preview=True
  elif z==6:
   if self.preview and self.queue==self.route and self.preview_pos==self.goal:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
