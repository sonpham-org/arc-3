"""q521 Pollen Frame -- moving local controls become their complement after wear."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MEADOW,POLLEN,FRAME,WAVE,WEAR,TARGET,BAD=15,7,9,12,14,10,6,8
LEVELS=[
 {"name":"Moving Frame","n":6,"start":0,"wear":2,"plan":[2,1,2]},
 {"name":"Translated Bloom","n":7,"start":2,"wear":2,"plan":[3,2,1,2]},
 {"name":"Wear Complement","n":8,"start":1,"wear":3,"plan":[2,3,1,2,1]},
 {"name":"Rotated Control","n":9,"start":4,"wear":3,"plan":[1,3,2,2,1,3]},
 {"name":"Global Alignment","n":10,"start":3,"wear":4,"plan":[2,1,3,2,1,2,3]},
 {"name":"Pollen Frame","n":11,"start":5,"wear":4,"plan":[3,2,1,3,2,2,1,3]}]
def advance(state,action,n,wear):
 pos,rot,steps=state
 if action==3:rot=(rot+1)%4
 else:
  d=-1 if action==1 else 1
  if rot%2:d=-d
  if steps>=wear:d=-d
  pos=(pos+d)%n
 return pos,rot,steps+1
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=MEADOW
  for i in range(g.n):x=7+i*(50//g.n);f[28:40,x:x+5]=FRAME
  for p,c in ((g.pos,POLLEN),(g.target,TARGET)):x=7+p*(50//g.n);f[18:24,x:x+6]=c
  f[44:49,8:8+g.rot*10]=WAVE;f[3:6,8:30]=WEAR if g.steps>=g.wear else MEADOW
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q521(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=1;self.pos=self.rot=self.steps=self.wear=self.target=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q521",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.pos=s["start"];self.wear=s["wear"];self.rot=self.steps=0;t=(self.pos,0,0)
  for a in s["plan"]:t=advance(t,a,self.n,self.wear)
  self.target=t[0];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.pos,self.rot,self.steps=advance((self.pos,self.rot,self.steps),z,self.n,self.wear)
  elif z==6:
   if self.pos==self.target and self.steps>=self.wear:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
