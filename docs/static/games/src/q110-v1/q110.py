"""q110 Moving Portal Frame -- portal exits remain fixed to moving carriers."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SEA,CARRIERA,CARRIERB,PORTAL,PLAYER,TARGET,BAD=3,10,9,12,15,6,14,8
LEVELS=[
 {"name":"Carrier Exit","mod":5,"bases":[0,3],"vel":[1,-1],"offset":[1,2],"start":0,"target":2},
 {"name":"Wait for the Frame","mod":6,"bases":[1,4],"vel":[1,-1],"offset":[2,1],"start":3,"target":5},
 {"name":"Two Moving Portals","mod":7,"bases":[0,5],"vel":[2,-1],"offset":[1,3],"start":2,"target":6},
 {"name":"Relative Exit","mod":8,"bases":[2,6],"vel":[1,-2],"offset":[3,1],"start":0,"target":7},
 {"name":"Composed Transport","mod":9,"bases":[1,7],"vel":[2,-1],"offset":[2,4],"start":4,"target":8},
 {"name":"Moving Portal Frame","mod":10,"bases":[3,8],"vel":[1,-3],"offset":[4,2],"start":1,"target":9}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=SEA;n=g.mod
  for i,(b,v) in enumerate(zip(g.bases,g.vel)):
   p=(b+v*g.phase)%n;x=7+p*(50//n);f[17+i*15:27+i*15,x:x+7]=CARRIERA if i==0 else CARRIERB;f[14+i*15:17+i*15,x+2:x+5]=PORTAL
  px=7+g.player*(50//n);tx=7+g.target*(50//n);f[49:54,px:px+6]=PLAYER;f[3:6,tx:tx+6]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q110(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.mod=1;self.bases=self.vel=self.offset=[];self.player=self.target=self.phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q110",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.mod=s["mod"];self.bases=list(s["bases"]);self.vel=list(s["vel"]);self.offset=list(s["offset"]);self.player=s["start"];self.target=s["target"];self.phase=0;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2):
   i=z-1;self.player=(self.bases[i]+self.vel[i]*self.phase+self.offset[i])%self.mod;self.phase=(self.phase+1)%self.mod
  elif z==5:self.phase=(self.phase+1)%self.mod
  elif z==6:
   if self.player==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
