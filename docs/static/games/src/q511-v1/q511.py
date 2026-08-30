"""q511 Tapestry Frame -- local shuttle motion in a moving, graph-rewriting frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,SHUTTLE,FRAME,SWITCH,GOAL,REWIRED,BAD=0,9,14,15,10,6,12,8
LEVELS=[
 {"name":"Moving Local Frame","n":6,"start":0,"switch":2,"goal":4},{"name":"Rotate the Loom","n":7,"start":1,"switch":4,"goal":0},
 {"name":"Global Alignment","n":8,"start":3,"switch":6,"goal":2},{"name":"Rewrite Adjacency","n":8,"start":0,"switch":5,"goal":3},
 {"name":"Crossing Tensions","n":9,"start":2,"switch":7,"goal":4},{"name":"Tapestry Frame","n":10,"start":1,"switch":6,"goal":8}]
def transition(state,action,n):
 pos,origin,rot,rewired=state
 if action in (1,2):
  step=-1 if action==1 else 1
  if rot%2:step=-step
  if rewired:step*=2
  pos=(pos+step)%n
 elif action==3:rot=(rot+1)%4
 origin=(origin+1)%n
 return pos,origin,rot,rewired
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=LOOM
  for i in range(g.n):x=7+i*(50//g.n);f[25:39,x:x+5]=REWIRED if g.rewired else FRAME
  for p,c in ((g.pos,SHUTTLE),(g.switch,SWITCH),(g.goal,GOAL)):x=7+p*(50//g.n);f[16:22,x:x+6]=c
  f[45:49,8:8+g.origin*5]=FRAME
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q511(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=1;self.pos=self.origin=self.rot=self.switch=self.goal=0;self.rewired=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q511",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.pos=s["start"];self.switch=s["switch"];self.goal=s["goal"];self.origin=self.rot=0;self.rewired=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.pos,self.origin,self.rot,self.rewired=transition((self.pos,self.origin,self.rot,self.rewired),z,self.n)
  elif z==5 and self.pos==self.switch:self.rewired=True;self.origin=(self.origin+1)%self.n
  elif z==6:
   if self.rewired and self.pos==self.goal:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
