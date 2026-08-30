"""q147 Affordance Sketch -- transform outlines to test fit before construction."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DESK,OUTLINE,OBJECT,FIT,MISS,CURSOR,BAD=14,1,15,9,10,8,11,6
LEVELS=[
 {"name":"Rotate the Outline","rotations":[1,0]}, {"name":"Sketch Two Tools","rotations":[3,1,0]},
 {"name":"Fit Before Build","rotations":[2,3,1]}, {"name":"Structural Preview","rotations":[1,2,3,0]},
 {"name":"Nested Affordance","rotations":[3,1,2,1,0]}, {"name":"Affordance Sketch","rotations":[2,3,1,2,0,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=DESK;n=len(g.rotations)
  for i,r in enumerate(g.current):x=7+i*(50//n);f[18:37,x:x+8]=OUTLINE;f[22+r*3:26+r*3,x+2:x+6]=OBJECT;f[13:16,x:x+8]=CURSOR if i==g.cursor else DESK;f[42:47,x:x+8]=FIT if g.preview and r==g.rotations[i] else MISS if g.preview else DESK
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q147(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.rotations=self.current=[];self.cursor=0;self.preview=self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q147",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):self.rotations=list(LEVELS[self.level_index]["rotations"]);self.current=[0]*len(self.rotations);self.cursor=0;self.preview=self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.current[self.cursor]=(self.current[self.cursor]+1)%4;self.preview=False
  elif z==3:self.cursor=(self.cursor-1)%len(self.current)
  elif z==4:self.cursor=(self.cursor+1)%len(self.current)
  elif z==5:self.preview=True
  elif z==6:
   if self.preview and self.current==self.rotations:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
