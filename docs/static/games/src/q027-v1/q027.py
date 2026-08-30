"""q027 Proxy Lever -- a causal role follows a slot rather than an object's identity."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,SLOT,OBJECT,LEVER,EFFECT,TARGET,BAD=6,1,3,10,12,14,9,8
LEVELS=[
 {"name":"Role Not Object","count":3,"role":1,"target":2},
 {"name":"Rotate Proxy","count":4,"role":2,"target":1},
 {"name":"Hidden Position","count":4,"role":1,"target":3},
 {"name":"Identity Transfer","count":5,"role":3,"target":1},
 {"name":"Causal Seat","count":6,"role":2,"target":5},
 {"name":"Proxy Lever","count":7,"role":4,"target":2}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=LAB;n=len(g.objects)
  for i,o in enumerate(g.objects):
   x=7+i*(49//n);f[19:38,x:x+7]=SLOT;f[23:34,x+1:x+6]=OBJECT+(o%3);f[41:45,x:x+7]=EFFECT if o==g.affected else LAB
  f[11:15,7:17]=LEVER;f[48:52,7:7+g.target*6]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q027(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.objects=[];self.role=self.target=0;self.affected=-1;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q027",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.objects=list(range(s["count"]));self.role=s["role"];self.target=s["target"];self.affected=-1;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.objects=self.objects[1:]+self.objects[:1]
  elif a==2:self.objects=self.objects[-1:]+self.objects[:-1]
  elif a==5:
   self.affected=self.objects[self.role]
   if self.affected==self.target:self.next_level()
  elif a==6:self.failed=True;self.lose()
  self.complete_action()
