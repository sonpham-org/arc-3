"""q505 Alloy Frame -- billet motion composed with translating rotating force lanes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,FRAME,LANE,TARGET,BAD=1,7,12,14,15,10,6,8
LEVELS=[{"name":n,"size":s,"plan":p} for n,s,p in [("Local Billet",6,[2,1,2]),("Rotating Lane",7,[3,2,1,2]),("Translating Force",8,[2,3,1,2,1]),("Edge Exchange",9,[1,3,2,2,1,3]),("Global Alignment",10,[2,1,3,2,1,2,3]),("Alloy Frame",11,[3,2,1,3,2,2,1,3])]]
def advance(s,z,n):
 pos,origin,rot=s
 if z==3:rot=(rot+1)%4

 else:pos=(pos+(-1 if z==1 else 1)*(-1 if rot%2 else 1)+origin)%n
 origin=(origin+1)%n;return pos,origin,rot
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for i in range(g.n):x=7+i*(50//g.n);f[22:35,x:x+5]=FORCE
  x=7+g.pos*(50//g.n);f[14:19,x:x+6]=BILLET;f[41:45,8:8+g.origin*5]=LANE;f[50:54,8:8+g.rot*11]=FRAME
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q505(ARCBaseGame):
 def __init__(self):self.display=D(self);self.n=1;self.pos=self.origin=self.rot=0;self.target=None;self.bad=False;ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q505",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,6])
 def on_set_level(self,l):
  x=LEVELS[self.level_index];self.n=x["size"];self.pos=self.origin=self.rot=0;s=(0,0,0)
  for z in x["plan"]:s=advance(s,z,self.n)
  self.target=s;self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z in (1,2,3):self.pos,self.origin,self.rot=advance((self.pos,self.origin,self.rot),z,self.n)
  elif z==6:
   if (self.pos,self.origin,self.rot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
