"""q501 Aurora Frame -- local motion composes with a translating hysteretic light frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ICE,MOTE,FRAME,CURTAIN,HYSTERESIS,TARGET,BAD=14,10,9,15,12,3,6,8
LEVELS=[
 {"name":"Translating Frame","n":6,"start":0,"plan":[2,1,2]},{"name":"Rotating Curtain","n":7,"start":2,"plan":[3,2,1,2]},
 {"name":"Visible Hysteresis","n":8,"start":1,"plan":[2,3,1,2,1]},{"name":"Local and Global","n":9,"start":4,"plan":[1,3,2,2,1,3]},
 {"name":"Edge Exchange","n":10,"start":3,"plan":[2,1,3,2,1,2,3]},{"name":"Aurora Frame","n":11,"start":5,"plan":[3,2,1,3,2,2,1,3]}]
def advance(state,action,n):
 pos,origin,rot,trail=state
 if action==3:rot=(rot+1)%4
 else:
  d=-1 if action==1 else 1
  if rot%2:d=-d
  pos=(pos+d+origin)%n
 origin=(origin+1)%n;trail=(trail+origin+rot)%n
 return pos,origin,rot,trail
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=ICE
  for i in range(g.n):x=7+i*(50//g.n);f[28:40,x:x+5]=FRAME
  for p,c in ((g.pos,MOTE),(g.target,TARGET)):x=7+p*(50//g.n);f[18:24,x:x+6]=c
  f[44:48,8:8+g.origin*5]=CURTAIN;f[49:53,8:8+g.trail*4]=HYSTERESIS
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q501(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.n=1;self.pos=self.origin=self.rot=self.trail=self.target=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q501",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.n=s["n"];self.pos=s["start"];self.origin=self.rot=self.trail=0;t=(self.pos,0,0,0)
  for a in s["plan"]:t=advance(t,a,self.n)
  self.target=t[0];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.pos,self.origin,self.rot,self.trail=advance((self.pos,self.origin,self.rot,self.trail),z,self.n)
  elif z==6:
   if self.pos==self.target and self.trail!=0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
